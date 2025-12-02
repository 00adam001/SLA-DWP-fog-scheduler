# simulation.py
# NOTE: Legacy simulation engine retained for reference.
# For validated results, use `run_corrected_simulation.py` and `plot_corrected_results.py`.
import random
from typing import Dict, Any

from config import SimulationConfig
from metrics import MetricsCollector
from request_generator import RequestGenerator
from topology import FogTopology, build_grid_topology


class Simulation:
    """
    Main simulation engine.
    Steps:
      - generate edge requests
      - route each to nearest fog node
      - enqueue if link capacity allows, else drop
      - process queues in FIFO within fog CPU capacity
      - collect metrics
    """

    def __init__(self, config: SimulationConfig) -> None:
        self.config = config

        # Seed randomness
        random.seed(self.config.random_seed)

        # Build components
        self.topology: FogTopology = build_grid_topology(self.config)
        self.generator = RequestGenerator(self.config)
        self.metrics = MetricsCollector()

    def _record_admission_control_metrics(self) -> None:
        """Collect admission control metrics from fog nodes (especially for DYNAMIC_PRIORITY).
        This should ONLY be called once at the end of simulation, not per-step!
        """
        # This is now called only in final_report collection, not in the main loop
        pass

    def run(self) -> Dict[str, Any]:
        time = 0.0
        # Support millisecond time steps: if `time_step_ms` is provided
        # in the config, use that (converted to seconds). Otherwise use
        # the `time_step` (seconds) field.
        if getattr(self.config, "time_step_ms", None) is not None:
            dt = float(self.config.time_step_ms) / 1000.0
        else:
            dt = self.config.time_step

        while time < self.config.sim_time:
            # 1) Reset per-step state on fog nodes (e.g., link usage)
            for node in self.topology.all_nodes():
                node.reset_step_state()

            # 2) Generate new requests at the edge
            new_requests = self.generator.generate_requests(time)
            self.metrics.record_generated(new_requests)

            # 3) Route each request to the nearest fog node
            for req in new_requests:
                fog_node = self.topology.get_nearest_fog(req.source_position)
                req.assigned_fog_id = fog_node.node_id

                # Link feasibility check (link capacity interpreted as MB/s)
                if fog_node.can_accept_request(req, dt):
                    enq_res = fog_node.enqueue_request(req, dt)
                    # Support both legacy bool and new (bool, reason) return forms
                    success = False
                    reason = None
                    if isinstance(enq_res, tuple):
                        success, reason = enq_res
                    else:
                        success = bool(enq_res)
                    if success:
                        # Successfully admitted to queue
                        self.metrics.total_admitted += 1
                    else:
                        # Differentiate between admission rejection vs queue full
                        if reason == "admission_rejected":
                            self.metrics.record_rejected(req, reason=reason)
                        else:
                            # Default to queue_full
                            self.metrics.record_dropped(req, reason="queue_full")
                else:
                    # Drop due to link capacity constraint
                    self.metrics.record_dropped(req, reason="link_capacity")

            # 4) Process requests at each fog node (FIFO)
            all_completed = []
            for node in self.topology.all_nodes():
                completed = node.process_one_step(current_time=time, time_step=dt)
                all_completed.extend(completed)

            self.metrics.record_completed(all_completed)

            # 5) Record queue lengths after processing
            self.metrics.record_queue_lengths(self.topology.all_nodes())

            # finalize per-step metrics and advance time
            self.metrics.step_advance()

            # Advance time
            time += dt

        # Collect admission control metrics (call once at end)
        for node in self.topology.all_nodes():
            if hasattr(node, 'total_rejected_due_to_deadline'):
                self.metrics.total_rejected_due_to_deadline += node.total_rejected_due_to_deadline
            if hasattr(node, 'total_offloaded_to_cloud'):
                self.metrics.total_offloaded_to_cloud += node.total_offloaded_to_cloud

        # 6) Return final metrics
        return self.metrics.final_report()
