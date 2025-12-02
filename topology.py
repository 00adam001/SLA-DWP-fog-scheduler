# topology.py
from __future__ import annotations
from collections import deque
from math import sqrt
from typing import Deque, List, Tuple, Dict, Optional

from config import SimulationConfig
from models import Request


class FogNode:
    """
    Represents a fog node located at an intersection (or region).
    It has:
    - a position
    - CPU capacity per time step
    - link capacity (MB per time step)
    - a queue of requests (can be FIFO or EMERGENCY_FIRST mode)
    """
    def __init__(
        self,
        node_id: int,
        position: Tuple[float, float],
        cpu_capacity: float,
        link_capacity: float | None = None,
        max_queue_length: int | None = None,
        scheduler: str = "FIFO",
    ) -> None:
        self.node_id = node_id
        self.position = position
        self.cpu_capacity = cpu_capacity
        self.link_capacity = link_capacity
        self.max_queue_length = max_queue_length
        self.scheduler = scheduler  # "FIFO", "EMERGENCY_FIRST", "STATIC_PRIORITY", or "SLA-DWP-Fog"

        # For FIFO mode: single queue
        self.queue: Deque[Request] = deque()
        
        # For EMERGENCY_FIRST mode: two separate queues
        self.emergency_queue: Deque[Request] = deque()
        self.normal_queue: Deque[Request] = deque()
        
        # For STATIC_PRIORITY mode: three priority queues
        # priority_class 3: Emergency, 2: Safety-Critical, 1: Non-Critical
        self.priority_queue_3: Deque[Request] = deque()  # Emergency
        self.priority_queue_2: Deque[Request] = deque()  # Safety-Critical
        self.priority_queue_1: Deque[Request] = deque()  # Non-Critical

        # For DYNAMIC_PRIORITY / SLA-DWP-Fog: per-class queues
        self.dynamic_queue_3: Deque[Request] = deque()  # Emergency
        self.dynamic_queue_2: Deque[Request] = deque()  # Safety-Critical
        self.dynamic_queue_1: Deque[Request] = deque()  # Non-Critical
        
        # SLA-Dynamic Priority Scheduler parameters
        # Priority weight coefficients (initialized uniformly)
        self.alpha = 1.0 / 3.0  # class importance weight
        self.beta = 1.0 / 3.0   # deadline urgency weight
        self.gamma = 1.0 / 3.0  # waiting time weight
        
        # Dual variables for Lagrangian optimization
        self.lambda_1 = 0.0     # for emergency deadline SLA
        self.lambda_2 = 0.0     # for latency SLA
        self.lambda_3 = 0.0     # for fairness SLA
        
        # SLA thresholds (configurable)
        self.sla_emergency_deadline_max = 0.1   # allow 10% emergency deadline violations
        self.sla_latency_max = 5000.0           # max acceptable latency in ms
        self.sla_fairness_max = 8000.0          # max acceptable normal-task latency in ms
        
        # Learning rates for dual variable updates
        self.eta_1 = 0.01
        self.eta_2 = 0.01
        self.eta_3 = 0.01
        
        # Sliding window for metrics (last N completed requests)
        self.window_size = 500
        self.completed_in_window: List[Request] = []
        # Time-based window tracking for SLA-DWP-Fog
        self._completed_history: List[Request] = []
        self._last_window_update: float = 0.0
        
        # Max waiting time threshold for normalization (seconds)
        self.max_wait_threshold = 10.0
        
        # Currently executing request (for potential preemption)
        self.current_request: Optional[Request] = None
        self.current_request_start_time: Optional[float] = None

        self.current_link_load: float = 0.0  # MB sent this time step
        
        # DYNAMIC_PRIORITY admission control metrics
        self.total_rejected_due_to_deadline: int = 0
        self.total_offloaded_to_cloud: int = 0

    def reset_step_state(self) -> None:
        """
        Reset per-step state, e.g., link load before new arrivals.
        """
        self.current_link_load = 0.0

    def can_accept_request(self, request: Request, time_step: float) -> bool:
        """
        Check simple link capacity constraint for this time step.
        `link_capacity` is interpreted as MB per second; allowed MB for
        this step is `link_capacity * time_step`.
        If `link_capacity` is None, always accept.
        """
        if self.link_capacity is None:
            return True
        capacity_this_step = self.link_capacity * time_step
        projected = self.current_link_load + request.data_size
        return projected <= capacity_this_step

    def enqueue_request(self, request: Request, time_step: float):
        """
        Enqueue the request according to the scheduler mode.
        - FIFO: add to single queue (with max_queue_length constraint)
        - EMERGENCY_FIRST: add to appropriate queue (emergency or normal)
        - STATIC_PRIORITY: add to queue matching priority_class (3, 2, or 1)
        - DYNAMIC_PRIORITY / SLA-DWP-Fog: add to per-class queue with SLA-aware admission control
        
        Returns:
            - True if enqueued successfully (legacy bool)
            - (True, None) if enqueued successfully (new form)
            - False if failed (legacy bool, treated as queue_full by caller)
            - (False, reason) where reason in {"queue_full", "admission_rejected"}
        """
        # Check if we have room (combined queue length)
        total_queue_len = self._get_total_queue_length()
        if self.max_queue_length is not None and total_queue_len >= self.max_queue_length:
            return False, "queue_full"
        
        if self.scheduler in ("DYNAMIC_PRIORITY", "SLA-DWP-Fog"):
            # SLA-DWP-Fog Admission Control: check if request can meet deadline
            if not self._admission_control_check_timebased(request):
                # Reject or offload
                self.total_rejected_due_to_deadline += 1
                # For now, count as rejected (not processing in cloud)
                return False, "admission_rejected"
            
            # Add to per-class queue
            if request.priority_class == 3:
                self.dynamic_queue_3.append(request)
            elif request.priority_class == 2:
                self.dynamic_queue_2.append(request)
            else:  # priority_class == 1
                self.dynamic_queue_1.append(request)
            
            # Optional preemption: if running task has lower score, preempt
            if self.current_request is not None:
                new_score = self._priority_score(request, request.arrival_time)
                run_score = self._priority_score(self.current_request, request.arrival_time)
                if new_score > run_score:
                    # Put current back to its queue front
                    if self.current_request.priority_class == 3:
                        self.dynamic_queue_3.appendleft(self.current_request)
                    elif self.current_request.priority_class == 2:
                        self.dynamic_queue_2.appendleft(self.current_request)
                    else:
                        self.dynamic_queue_1.appendleft(self.current_request)
                    # Remove the newly enqueued request from its queue (now running)
                    if request.priority_class == 3:
                        self.dynamic_queue_3.pop()  # last appended
                    elif request.priority_class == 2:
                        self.dynamic_queue_2.pop()
                    else:
                        self.dynamic_queue_1.pop()
                    self.current_request = request
                    if self.current_request.start_time is None:
                        self.current_request.start_time = request.arrival_time
            return True, None
        elif self.scheduler == "STATIC_PRIORITY":
            # Add to queue matching priority_class
            if request.priority_class == 3:
                self.priority_queue_3.append(request)
            elif request.priority_class == 2:
                self.priority_queue_2.append(request)
            else:  # priority_class == 1
                self.priority_queue_1.append(request)
        elif self.scheduler == "EMERGENCY_FIRST":
            # Add to appropriate queue based on emergency status
            if request.is_emergency:
                self.emergency_queue.append(request)
            else:
                self.normal_queue.append(request)
        else:
            # FIFO mode: single queue with finite length constraint
            if self.max_queue_length is not None and len(self.queue) >= self.max_queue_length:
                return False, "queue_full"
            self.queue.append(request)
        
        if self.link_capacity is not None:
            self.current_link_load += request.data_size
        return True, None

    def _get_total_queue_length(self) -> int:
        """Helper to compute total queue length across all queues based on scheduler."""
        if self.scheduler in ("DYNAMIC_PRIORITY", "SLA-DWP-Fog"):
            return len(self.dynamic_queue_3) + len(self.dynamic_queue_2) + len(self.dynamic_queue_1) + (1 if self.current_request is not None else 0)
        elif self.scheduler == "STATIC_PRIORITY":
            return len(self.priority_queue_3) + len(self.priority_queue_2) + len(self.priority_queue_1)
        elif self.scheduler == "EMERGENCY_FIRST":
            return len(self.emergency_queue) + len(self.normal_queue)
        else:
            return len(self.queue)

    # ========== SLA-Dynamic Priority / SLA-DWP-Fog Helper Methods ==========
    
    def _admission_control_check_timebased(self, request: Request) -> bool:
        """Admission control: t_finish = a_i + (Wn + c_i)/C_n <= d_i."""
        total_remaining = 0.0
        for queue in (self.dynamic_queue_3, self.dynamic_queue_2, self.dynamic_queue_1):
            for req in queue:
                total_remaining += req.remaining_demand
        if self.current_request is not None:
            total_remaining += self.current_request.remaining_demand
        predicted_work_time = (total_remaining + request.processing_demand) / self.cpu_capacity
        predicted_finish = request.arrival_time + predicted_work_time
        return predicted_finish <= request.absolute_deadline
    
    def _select_edf_from_class(self, queue: Deque[Request]) -> Optional[Request]:
        """
        Select request with earliest deadline (EDF) from a class queue.
        Returns the request with minimum absolute_deadline, or None if queue empty.
        """
        if not queue:
            return None
        
        best_req = None
        earliest_deadline = float('inf')
        
        for req in queue:
            if req.absolute_deadline < earliest_deadline:
                earliest_deadline = req.absolute_deadline
                best_req = req
        
        return best_req
    
    def _select_next_request_sla(self, current_time: float) -> Optional[Request]:
        """Select next request by argmax of π_i(t) across all queued tasks with tie-breaks."""
        candidates: List[Request] = []
        for q in (self.dynamic_queue_3, self.dynamic_queue_2, self.dynamic_queue_1):
            candidates.extend(list(q))
        if not candidates:
            return None
        best_req = None
        best_score = -float("inf")
        for req in candidates:
            score = self._priority_score(req, current_time)
            if score > best_score:
                best_score = score
                best_req = req
            elif score == best_score and best_req is not None:
                # Tie-breaker: smaller slack (d_i - t), then larger waiting time
                slack_best = best_req.absolute_deadline - current_time
                slack_new = req.absolute_deadline - current_time
                if slack_new < slack_best:
                    best_req = req
                elif slack_new == slack_best:
                    wait_best = current_time - best_req.arrival_time
                    wait_new = current_time - req.arrival_time
                    if wait_new > wait_best:
                        best_req = req
        return best_req
    
    def _priority_score(self, request: Request, current_time: float) -> float:
        """π_i(t) = α g(κ_i) + β u_i(t) + γ w_i(t) with bounded components."""
        # g(κ): class importance mapping
        if request.priority_class == 3:
            g = 1.0
        elif request.priority_class == 2:
            g = 0.5
        else:
            g = 0.0

        # u_i(t) = min(1, max(0, 1 - (d_i - t)/D_i))
        Di = max(1e-9, request.relative_deadline_s)
        u = 1.0 - (request.absolute_deadline - current_time) / Di
        u = min(1.0, max(0.0, u))

        # w_i(t) = min(1, (t - a_i)/D_i)
        w = (current_time - request.arrival_time) / Di
        w = min(1.0, max(0.0, w))

        return self.alpha * g + self.beta * u + self.gamma * w
    
    def _select_next_request_dynamic_old(self, current_time: float) -> Optional[Request]:
        """
        [DEPRECATED] Old method - kept for reference.
        Select the next request from flat dynamic_queue with highest priority score.
        """
        # This is now replaced by _select_next_request_dynamic_edf
        # which uses per-class queues and EDF within each class.
        return None
    
    def _update_sla_weights_window(self, current_time: float) -> None:
        """Time-window SLA metrics and dual updates; update α,β,γ for next window."""
        # Pull parameters if set on node; otherwise use reasonable defaults
        TW = getattr(self, "sla_window_TW", 10.0)
        J1_max = getattr(self, "sla_J1_max", 0.10)
        J2_max_s = getattr(self, "sla_J2_max_s", 5.0)
        J3_max = getattr(self, "sla_J3_max", 2.0)
        eta1 = getattr(self, "sla_eta1", self.eta_1)
        eta2 = getattr(self, "sla_eta2", self.eta_2)
        eta3 = getattr(self, "sla_eta3", self.eta_3)
        eps = getattr(self, "sla_eps", 1e-6)

        # Filter recent completions within last TW seconds
        window_tasks = [r for r in self._completed_history if r.completion_time is not None and r.completion_time >= current_time - TW]
        if not window_tasks:
            return

        # J1: emergency miss ratio
        emer = [r for r in window_tasks if r.priority_class == 3]
        if emer:
            missed = sum(1 for r in emer if r.deadline_met() is False)
            J1 = missed / len(emer)
        else:
            J1 = 0.0

        # J2: mean end-to-end latency (seconds)
        lats = [r.latency() for r in window_tasks if r.latency() is not None]
        J2 = (sum(lats) / len(lats)) if lats else 0.0

        # J3: fairness ratio (mean latency Normal / Emergency); if undefined, set 1.0
        normal = [r.latency() for r in window_tasks if r.priority_class == 1 and r.latency() is not None]
        emer_l = [r.latency() for r in window_tasks if r.priority_class == 3 and r.latency() is not None]
        if emer_l and normal:
            J3 = (sum(normal) / len(normal)) / max(1e-9, (sum(emer_l) / len(emer_l)))
        else:
            J3 = 1.0

        # Dual updates (clamped to >=0)
        self.lambda_1 = max(0.0, self.lambda_1 + eta1 * (J1 - J1_max))
        self.lambda_2 = max(0.0, self.lambda_2 + eta2 * (J2 - J2_max_s))
        self.lambda_3 = max(0.0, self.lambda_3 + eta3 * (J3 - J3_max))

        # Normalize to weights α,β,γ
        S = (self.lambda_1 + eps) + (self.lambda_2 + eps) + (self.lambda_3 + eps)
        self.alpha = (self.lambda_1 + eps) / S
        self.beta = (self.lambda_2 + eps) / S
        self.gamma = (self.lambda_3 + eps) / S

    def process_one_step(self, current_time: float, time_step: float) -> List[Request]:
        """
        Process requests in the appropriate order for this time step, respecting CPU capacity.
        - FIFO: process single queue in arrival order
        - EMERGENCY_FIRST: process emergency_queue first, then normal_queue
        - STATIC_PRIORITY: process priority_queue_3 first, then priority_queue_2, then priority_queue_1
        - DYNAMIC_PRIORITY: select highest priority_score request at each step
        
        Returns:
            A list of completed requests in this time step.
        """
        completed: List[Request] = []
        capacity_left = self.cpu_capacity * time_step

        if self.scheduler in ("DYNAMIC_PRIORITY", "SLA-DWP-Fog"):
            # SLA-DWP-Fog: global priority by π_i(t), with time-window SLA adaptation
            while capacity_left > 0:
                # First, continue processing current request if any
                if self.current_request is not None:
                    if self.current_request.remaining_demand <= capacity_left:
                        capacity_used = self.current_request.remaining_demand
                        capacity_left -= capacity_used
                        self.current_request.remaining_demand = 0.0
                        self.current_request.completion_time = current_time + time_step
                        completed.append(self.current_request)
                        # Track completion history for SLA time-window
                        self._completed_history.append(self.current_request)
                        
                        self.current_request = None
                        self.current_request_start_time = None
                    else:
                        self.current_request.remaining_demand -= capacity_left
                        capacity_left = 0.0
                        break
                
                # Select next highest-priority request by π_i(t)
                next_req = self._select_next_request_sla(current_time)
                if next_req is None:
                    break
                
                # Remove from appropriate class queue
                if next_req.priority_class == 3:
                    self.dynamic_queue_3.remove(next_req)
                elif next_req.priority_class == 2:
                    self.dynamic_queue_2.remove(next_req)
                else:
                    self.dynamic_queue_1.remove(next_req)
                
                # Start processing
                if next_req.start_time is None:
                    next_req.start_time = current_time
                
                self.current_request = next_req
                self.current_request_start_time = current_time
            # Update SLA weights at time-window boundaries
            TW = getattr(self, "sla_window_TW", 10.0)
            if current_time - self._last_window_update >= TW:
                self._update_sla_weights_window(current_time)
                self._last_window_update = current_time
        
        elif self.scheduler == "STATIC_PRIORITY":
            # Process in priority order: 3 -> 2 -> 1
            for queue in [self.priority_queue_3, self.priority_queue_2, self.priority_queue_1]:
                while queue and capacity_left > 0:
                    req = queue[0]
                    if req.start_time is None:
                        req.start_time = current_time
                    
                    if req.remaining_demand <= capacity_left:
                        capacity_used = req.remaining_demand
                        capacity_left -= capacity_used
                        req.remaining_demand = 0.0
                        req.completion_time = current_time + time_step
                        completed.append(req)
                        queue.popleft()
                    else:
                        req.remaining_demand -= capacity_left
                        capacity_left = 0.0
        
        elif self.scheduler == "EMERGENCY_FIRST":
            # Process emergency queue first
            while self.emergency_queue and capacity_left > 0:
                req = self.emergency_queue[0]
                if req.start_time is None:
                    req.start_time = current_time
                
                if req.remaining_demand <= capacity_left:
                    capacity_used = req.remaining_demand
                    capacity_left -= capacity_used
                    req.remaining_demand = 0.0
                    req.completion_time = current_time + time_step
                    completed.append(req)
                    self.emergency_queue.popleft()
                else:
                    req.remaining_demand -= capacity_left
                    capacity_left = 0.0
            
            # Process normal queue with remaining capacity
            while self.normal_queue and capacity_left > 0:
                req = self.normal_queue[0]
                if req.start_time is None:
                    req.start_time = current_time
                
                if req.remaining_demand <= capacity_left:
                    capacity_used = req.remaining_demand
                    capacity_left -= capacity_used
                    req.remaining_demand = 0.0
                    req.completion_time = current_time + time_step
                    completed.append(req)
                    self.normal_queue.popleft()
                else:
                    req.remaining_demand -= capacity_left
                    capacity_left = 0.0
        
        else:
            # FIFO mode: process single queue
            while self.queue and capacity_left > 0:
                req = self.queue[0]
                if req.start_time is None:
                    req.start_time = current_time
                
                if req.remaining_demand <= capacity_left:
                    capacity_used = req.remaining_demand
                    capacity_left -= capacity_used
                    req.remaining_demand = 0.0
                    req.completion_time = current_time + time_step
                    completed.append(req)
                    self.queue.popleft()
                else:
                    req.remaining_demand -= capacity_left
                    capacity_left = 0.0

        return completed

    def queue_length(self) -> int:
        """Return total queue length (combined for multi-queue modes)."""
        return self._get_total_queue_length()


class FogTopology:
    """
    Container for all fog nodes and nearest-node lookup.
    """
    def __init__(self, fog_nodes: List[FogNode]) -> None:
        self.fog_nodes = fog_nodes

    def all_nodes(self) -> List[FogNode]:
        return self.fog_nodes

    def get_nearest_fog(self, position: Tuple[float, float]) -> FogNode:
        """
        Returns the fog node closest (Euclidean) to the given position.
        """
        best_node = None
        best_dist = float("inf")

        for node in self.fog_nodes:
            dx = node.position[0] - position[0]
            dy = node.position[1] - position[1]
            dist = sqrt(dx * dx + dy * dy)
            if dist < best_dist:
                best_dist = dist
                best_node = node

        assert best_node is not None
        return best_node


def build_grid_topology(config: SimulationConfig) -> FogTopology:
    """
    Build a simple grid of fog nodes over the rectangular city area.

    Nodes are placed evenly in a num_fog_nodes_x by num_fog_nodes_y grid.
    All nodes use the scheduler specified in config.
    """
    fog_nodes: List[FogNode] = []

    if config.num_fog_nodes_x <= 0 or config.num_fog_nodes_y <= 0:
        raise ValueError("Number of fog nodes in each dimension must be positive.")

    step_x = config.city_width / (config.num_fog_nodes_x + 1)
    step_y = config.city_height / (config.num_fog_nodes_y + 1)

    node_id = 0
    for ix in range(config.num_fog_nodes_x):
        for iy in range(config.num_fog_nodes_y):
            x = (ix + 1) * step_x
            y = (iy + 1) * step_y
            node = FogNode(
                node_id=node_id,
                position=(x, y),
                cpu_capacity=config.fog_cpu_capacity,
                link_capacity=config.fog_link_capacity,
                max_queue_length=getattr(config, "fog_max_queue_length", None),
                scheduler=getattr(config, "scheduler", "FIFO"),
            )
            # Wire SLA-DWP-Fog parameters onto node (if present on config)
            for attr in [
                "sla_window_TW",
                "sla_J1_max",
                "sla_J2_max_s",
                "sla_J3_max",
                "sla_eta1",
                "sla_eta2",
                "sla_eta3",
                "sla_eps",
            ]:
                if hasattr(config, attr):
                    setattr(node, attr, getattr(config, attr))
            fog_nodes.append(node)
            node_id += 1

    return FogTopology(fog_nodes)
