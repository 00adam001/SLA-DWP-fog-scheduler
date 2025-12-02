# metrics.py
from collections import defaultdict
from typing import Dict, List

from models import Request, RequestType
from topology import FogNode


class MetricsCollector:
    """
    Tracks simulation statistics and computes final summary.
    """

    def __init__(self) -> None:
        self.total_generated: int = 0
        self.total_completed: int = 0
        self.total_dropped: int = 0
        self.total_admitted: int = 0
        self.total_rejected: int = 0  # Admission-control rejections (never queued)

        # Dropped breakdown by reason
        self.dropped_by_reason: Dict[str, int] = defaultdict(int)

        # Per-type counts
        self.generated_by_type: Dict[RequestType, int] = defaultdict(int)
        self.completed_by_type: Dict[RequestType, int] = defaultdict(int)
        self.dropped_by_type: Dict[RequestType, int] = defaultdict(int)

        # Latencies of completed requests
        self.latencies: List[float] = []

        # Per-step series for time-series analysis
        self.per_step_generated: List[int] = []
        self.per_step_completed: List[int] = []
        self.per_step_dropped: List[int] = []
        # Temporary counter for drops within the current step
        self._current_step_dropped: int = 0

        # Queue lengths over time
        self.avg_queue_lengths: List[float] = []
        self.max_queue_lengths: List[int] = []

        # Per-class metrics (Emergency vs Non-Emergency)
        self.emergency_generated: int = 0
        self.emergency_completed: int = 0
        self.emergency_dropped: int = 0
        self.emergency_latencies: List[float] = []

        self.normal_generated: int = 0
        self.normal_completed: int = 0
        self.normal_dropped: int = 0
        self.normal_latencies: List[float] = []

        # Waiting times by priority class (seconds)
        self.waiting_times_emergency: List[float] = []
        self.waiting_times_safety: List[float] = []
        self.waiting_times_normal: List[float] = []

        # QoS / Deadline-related metrics
        # Overall deadline tracking
        self.total_deadline_met: int = 0
        self.total_deadline_violated: int = 0

        # Per-priority-class deadline tracking
        # Priority class: 3=Emergency, 2=Safety-critical, 1=Non-critical
        self.priority3_deadline_met: int = 0  # Emergency-class
        self.priority3_deadline_violated: int = 0
        self.priority2_deadline_met: int = 0  # Safety-critical
        self.priority2_deadline_violated: int = 0
        self.priority1_deadline_met: int = 0  # Non-critical
        self.priority1_deadline_violated: int = 0
        
        # SLA-DWP-Fog admission control metrics (kept for backward compatibility)
        self.total_rejected_due_to_deadline: int = 0
        self.total_offloaded_to_cloud: int = 0

    def record_generated(self, requests: List[Request]) -> None:
        self.total_generated += len(requests)
        # record per-step generated count
        self.per_step_generated.append(len(requests))
        for r in requests:
            self.generated_by_type[r.request_type] += 1
            # Track per-class
            if r.is_emergency:
                self.emergency_generated += 1
            else:
                self.normal_generated += 1

    def record_completed(self, requests: List[Request]) -> None:
        self.total_completed += len(requests)
        # record per-step completed count
        self.per_step_completed.append(len(requests))
        for r in requests:
            self.completed_by_type[r.request_type] += 1
            lat = r.latency()
            if lat is not None:
                self.latencies.append(lat)
                # Track per-class (Emergency vs Non-Emergency)
                if r.is_emergency:
                    self.emergency_completed += 1
                    self.emergency_latencies.append(lat)
                else:
                    self.normal_completed += 1
                    self.normal_latencies.append(lat)
            
            # Track waiting time by priority class if start_time exists
            if r.start_time is not None:
                waiting = r.start_time - r.arrival_time
                if r.priority_class == 3:
                    self.waiting_times_emergency.append(waiting)
                elif r.priority_class == 2:
                    self.waiting_times_safety.append(waiting)
                else:
                    self.waiting_times_normal.append(waiting)
            
            # Track QoS deadline compliance
            deadline_met = r.deadline_met()
            if deadline_met is not None:
                if deadline_met:
                    self.total_deadline_met += 1
                else:
                    self.total_deadline_violated += 1
                
                # Track by priority class
                if r.priority_class == 3:  # Emergency-class
                    if deadline_met:
                        self.priority3_deadline_met += 1
                    else:
                        self.priority3_deadline_violated += 1
                elif r.priority_class == 2:  # Safety-critical
                    if deadline_met:
                        self.priority2_deadline_met += 1
                    else:
                        self.priority2_deadline_violated += 1
                elif r.priority_class == 1:  # Non-critical
                    if deadline_met:
                        self.priority1_deadline_met += 1
                    else:
                        self.priority1_deadline_violated += 1

    def record_dropped(self, request: Request, reason: str) -> None:
        self.total_dropped += 1
        self.dropped_by_type[request.request_type] += 1
        self.dropped_by_reason[reason] += 1
        # increment per-step drop counter
        self._current_step_dropped += 1
        # Track per-class
        if request.is_emergency:
            self.emergency_dropped += 1
        else:
            self.normal_dropped += 1

    def record_rejected(self, request: Request, reason: str = "admission_control") -> None:
        """Record a request that failed admission (never queued)."""
        self.total_rejected += 1
        self.dropped_by_reason[reason] += 1
        # Track per-class for visibility (treated like dropped but separate counter)
        if request.is_emergency:
            self.emergency_dropped += 1
        else:
            self.normal_dropped += 1

    def record_queue_lengths(self, fog_nodes: List[FogNode]) -> None:
        if not fog_nodes:
            return
        lengths = [node.queue_length() for node in fog_nodes]
        avg_len = sum(lengths) / len(lengths)
        max_len = max(lengths)
        self.avg_queue_lengths.append(avg_len)
        self.max_queue_lengths.append(max_len)

    def step_advance(self) -> None:
        """Call at the end of each simulation step to finalize per-step counters."""
        # Append the number of drops that happened in this step
        self.per_step_dropped.append(self._current_step_dropped)
        # reset counter for next step
        self._current_step_dropped = 0

    def final_report(self) -> Dict[str, object]:
        """
        Compute summary statistics and return as a dictionary.
        """
        avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else None
        max_latency = max(self.latencies) if self.latencies else None

        avg_queue_len_overall = (
            sum(self.avg_queue_lengths) / len(self.avg_queue_lengths)
            if self.avg_queue_lengths
            else None
        )
        max_queue_len_overall = max(self.max_queue_lengths) if self.max_queue_lengths else None

        completion_ratio = (
            self.total_completed / self.total_generated
            if self.total_generated > 0
            else None
        )

        # Per-class metrics
        emergency_avg_latency = (
            sum(self.emergency_latencies) / len(self.emergency_latencies)
            if self.emergency_latencies
            else None
        )
        normal_avg_latency = (
            sum(self.normal_latencies) / len(self.normal_latencies)
            if self.normal_latencies
            else None
        )

        emergency_completion_ratio = (
            self.emergency_completed / self.emergency_generated
            if self.emergency_generated > 0
            else None
        )
        normal_completion_ratio = (
            self.normal_completed / self.normal_generated
            if self.normal_generated > 0
            else None
        )

        return {
            "total_generated": self.total_generated,
            "total_completed": self.total_completed,
            "total_dropped": self.total_dropped,
            "total_admitted": self.total_admitted,
            "total_rejected": self.total_rejected,
            "completion_ratio": completion_ratio,
            "avg_latency": avg_latency,
            "max_latency": max_latency,
            "avg_queue_length": avg_queue_len_overall,
            "max_queue_length": max_queue_len_overall,
            # include raw series for plotting
            "avg_queue_lengths": list(self.avg_queue_lengths),
            "max_queue_lengths": list(self.max_queue_lengths),
            "per_step_generated": list(self.per_step_generated),
            "per_step_completed": list(self.per_step_completed),
            "per_step_dropped": list(self.per_step_dropped),
            "latencies": list(self.latencies),
            "generated_by_type": {k.name: v for k, v in self.generated_by_type.items()},
            "completed_by_type": {k.name: v for k, v in self.completed_by_type.items()},
            "dropped_by_type": {k.name: v for k, v in self.dropped_by_type.items()},
            "dropped_by_reason": dict(self.dropped_by_reason),
            # Per-class metrics
            "emergency_generated": self.emergency_generated,
            "emergency_completed": self.emergency_completed,
            "emergency_dropped": self.emergency_dropped,
            "emergency_avg_latency": emergency_avg_latency,
            "emergency_completion_ratio": emergency_completion_ratio,
            "emergency_latencies": list(self.emergency_latencies),
            "normal_generated": self.normal_generated,
            "normal_completed": self.normal_completed,
            "normal_dropped": self.normal_dropped,
            "normal_avg_latency": normal_avg_latency,
            "normal_completion_ratio": normal_completion_ratio,
            "normal_latencies": list(self.normal_latencies),
            # Waiting time distributions (seconds)
            "waiting_times_emergency": list(self.waiting_times_emergency),
            "waiting_times_safety": list(self.waiting_times_safety),
            "waiting_times_normal": list(self.waiting_times_normal),
            # QoS / Deadline metrics
            "total_deadline_met": self.total_deadline_met,
            "total_deadline_violated": self.total_deadline_violated,
            "overall_deadline_met_rate": self.overall_deadline_met_rate(),
            "priority3_deadline_met": self.priority3_deadline_met,
            "priority3_deadline_violated": self.priority3_deadline_violated,
            "priority3_deadline_met_rate": self.priority3_deadline_met_rate(),
            "priority2_deadline_met": self.priority2_deadline_met,
            "priority2_deadline_violated": self.priority2_deadline_violated,
            "priority2_deadline_met_rate": self.priority2_deadline_met_rate(),
            "priority1_deadline_met": self.priority1_deadline_met,
            "priority1_deadline_violated": self.priority1_deadline_violated,
            "priority1_deadline_met_rate": self.priority1_deadline_met_rate(),
            # DYNAMIC_PRIORITY admission control metrics
            "total_rejected_due_to_deadline": self.total_rejected_due_to_deadline,
            "total_offloaded_to_cloud": self.total_offloaded_to_cloud,
        }

    def overall_deadline_met_rate(self) -> float:
        """Get overall QoS deadline met rate"""
        total = self.total_deadline_met + self.total_deadline_violated
        if total == 0:
            return 0.0
        return self.total_deadline_met / total

    def priority3_deadline_met_rate(self) -> float:
        """Get Emergency-class deadline met rate"""
        total = self.priority3_deadline_met + self.priority3_deadline_violated
        if total == 0:
            return 0.0
        return self.priority3_deadline_met / total

    def priority2_deadline_met_rate(self) -> float:
        """Get Safety-critical deadline met rate"""
        total = self.priority2_deadline_met + self.priority2_deadline_violated
        if total == 0:
            return 0.0
        return self.priority2_deadline_met / total

    def priority1_deadline_met_rate(self) -> float:
        """Get Non-critical deadline met rate"""
        total = self.priority1_deadline_met + self.priority1_deadline_violated
        if total == 0:
            return 0.0
        return self.priority1_deadline_met / total

    def get_admission_rate(self) -> float:
        """
        Get overall admission rate as a fraction between 0 and 1.
        
        Returns:
            float: total_admitted / total_generated, or 0.0 if no requests generated
        """
        if self.total_generated == 0:
            return 0.0
        return self.total_admitted / self.total_generated