# request_generator.py
import random
from typing import List, Tuple

from config import SimulationConfig
from models import Request, RequestType


class RequestGenerator:
    """
    Generates synthetic edge requests based on:
    - approximate Poisson-like arrivals per time step
    - per-type probabilities and default resource parameters
    """

    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.next_request_id = 0

        # Probability distribution over request types (should sum to ~1.0)
        # You can tweak these to change mix of services.
        # Increased emergency-type frequency to 25-30% for meaningful scheduler testing
        self.type_probabilities: List[Tuple[RequestType, float]] = [
            (RequestType.LANE_GUIDANCE, 0.08),
            (RequestType.NAVIGATION_REROUTING, 0.08),
            (RequestType.PARKING_DISCOVERY, 0.05),
            (RequestType.EV_CHARGER_BOOKING, 0.03),
            (RequestType.TOLLING_CHARGING, 0.02),
            (RequestType.EMERGENCY_SOS, 0.10),           # Increased from 0.02
            (RequestType.INCIDENT_UPLOAD, 0.08),         # Increased from 0.03
            (RequestType.COLLISION_ALERT, 0.08),         # Increased from 0.02
            (RequestType.SPEED_LIMIT_AR, 0.08),
            (RequestType.ROAD_HAZARD_BROADCAST, 0.10),   # Increased from 0.05
            (RequestType.DROWSINESS_ALERT, 0.05),
            (RequestType.SURROUND_VIEW, 0.05),
            (RequestType.SCHOOL_ZONE_ADVISORY, 0.02),
            (RequestType.WEATHER_AWARE_ROUTING, 0.02),
            (RequestType.TRIP_SUMMARY_ANALYTICS, 0.00),  # Reduced from 0.07
        ]

        # Normalize probabilities in case they don't sum exactly to 1.0
        total_p = sum(p for _, p in self.type_probabilities)
        if total_p <= 0:
            raise ValueError("Sum of type probabilities must be positive.")
        self.type_probabilities = [
            (rt, p / total_p) for rt, p in self.type_probabilities
        ]

    def _sample_request_type(self) -> RequestType:
        """
        Sample a request type according to the defined probabilities.
        """
        r = random.random()
        cumulative = 0.0
        for rt, p in self.type_probabilities:
            cumulative += p
            if r <= cumulative:
                return rt
        # fallback
        return self.type_probabilities[-1][0]

    def _defaults_for_type(
        self, request_type: RequestType
    ) -> tuple[float, float, float | None, bool]:
        """
        Returns (processing_demand, data_size, latency_slo, is_emergency)
        with simple, interpretable defaults for each request type.
        Units:
        - processing_demand: CPU units
        - data_size: MB
        - latency_slo: seconds (soft deadline)
        """

        # These numbers are arbitrary but reasonable; you can tweak them
        # based on how heavy each service feels.
        if request_type == RequestType.EMERGENCY_SOS:
            return (20.0, 2.0, 2.0, True)
        if request_type == RequestType.COLLISION_ALERT:
            return (15.0, 1.5, 0.5, True)
        if request_type == RequestType.ROAD_HAZARD_BROADCAST:
            return (12.0, 1.0, 1.0, True)
        if request_type == RequestType.INCIDENT_UPLOAD:
            return (18.0, 10.0, 5.0, True)

        # Non-emergency but latency-sensitive
        if request_type in (
            RequestType.LANE_GUIDANCE,
            RequestType.NAVIGATION_REROUTING,
            RequestType.SPEED_LIMIT_AR,
            RequestType.DROWSINESS_ALERT,
            RequestType.SURROUND_VIEW,
            RequestType.SCHOOL_ZONE_ADVISORY,
            RequestType.WEATHER_AWARE_ROUTING,
        ):
            return (10.0, 1.0, 3.0, False)

        # Medium priority services
        if request_type in (
            RequestType.PARKING_DISCOVERY,
            RequestType.EV_CHARGER_BOOKING,
            RequestType.TOLLING_CHARGING,
        ):
            return (8.0, 1.0, 5.0, False)

        # Long-term analytics, low priority
        if request_type == RequestType.TRIP_SUMMARY_ANALYTICS:
            return (5.0, 3.0, 60.0, False)

        # Default fallback
        return (8.0, 1.0, None, False)

    def _priority_class_for_type(self, request_type: RequestType) -> int:
        """
        Returns priority_class (3=Emergency, 2=Safety-critical, 1=Non-critical)
        based on request type.
        
        This mapping determines QoS priority for deadline-aware scheduling.
        """
        # Emergency-class: highest priority (3)
        if request_type in (
            RequestType.EMERGENCY_SOS,
            RequestType.COLLISION_ALERT,
            RequestType.ROAD_HAZARD_BROADCAST,
            RequestType.INCIDENT_UPLOAD,
        ):
            return 3
        
        # Safety-critical: medium priority (2)
        if request_type in (
            RequestType.LANE_GUIDANCE,
            RequestType.NAVIGATION_REROUTING,
            RequestType.SPEED_LIMIT_AR,
            RequestType.DROWSINESS_ALERT,
            RequestType.SURROUND_VIEW,
            RequestType.SCHOOL_ZONE_ADVISORY,
            RequestType.WEATHER_AWARE_ROUTING,
            RequestType.PARKING_DISCOVERY,
        ):
            return 2
        
        # Non-critical: lowest priority (1)
        return 1

    def _relative_deadline_for_type(self, request_type: RequestType) -> float:
        """
        Returns relative_deadline_s (target max end-to-end latency in seconds)
        based on request type.
        
        Default mapping:
        - Emergency-class (priority 3): 5–10 seconds
        - Safety-critical (priority 2): 15–30 seconds
        - Non-critical (priority 1): 60–120 seconds
        """
        if request_type == RequestType.COLLISION_ALERT:
            return 5.0  # Ultra-tight: collision avoidance must be fastest
        if request_type in (
            RequestType.EMERGENCY_SOS,
            RequestType.ROAD_HAZARD_BROADCAST,
        ):
            return 8.0  # Emergency services need quick response
        if request_type == RequestType.INCIDENT_UPLOAD:
            return 10.0  # Emergency but slightly more flexible (data upload)
        
        # Safety-critical services: 15-30 second window
        if request_type in (
            RequestType.LANE_GUIDANCE,
            RequestType.DROWSINESS_ALERT,
            RequestType.SURROUND_VIEW,
        ):
            return 15.0  # Real-time vision/detection systems
        if request_type in (
            RequestType.NAVIGATION_REROUTING,
            RequestType.SPEED_LIMIT_AR,
            RequestType.SCHOOL_ZONE_ADVISORY,
            RequestType.WEATHER_AWARE_ROUTING,
        ):
            return 20.0  # Information-delivery services
        if request_type == RequestType.PARKING_DISCOVERY:
            return 25.0  # User-facing but not life-critical
        
        # Non-critical services: flexible (60-120 second window)
        if request_type in (
            RequestType.EV_CHARGER_BOOKING,
            RequestType.TOLLING_CHARGING,
        ):
            return 60.0  # Financial/infrastructure transactions
        if request_type == RequestType.TRIP_SUMMARY_ANALYTICS:
            return 120.0  # Batch processing, very flexible
        
        # Default fallback
        return 60.0

    def generate_requests(self, current_time: float) -> List[Request]:
        """
        Generate a list of new requests for the current time step.
        We approximate a Poisson process by performing Bernoulli trials.
        """
        avg = self.config.avg_requests_per_step
        max_n = self.config.max_requests_per_step
        if max_n <= 0:
            return []

        # Probability that a "slot" generates a request
        p = min(1.0, avg / float(max_n)) if avg > 0 else 0.0

        num_new = 0
        for _ in range(max_n):
            if random.random() < p:
                num_new += 1

        requests: List[Request] = []
        for _ in range(num_new):
            rt = self._sample_request_type()
            proc_cost, data_size, latency_slo, is_emergency = self._defaults_for_type(rt)

            # Random position in city area
            x = random.uniform(0.0, self.config.city_width)
            y = random.uniform(0.0, self.config.city_height)

            # Compute QoS fields
            priority_class = self._priority_class_for_type(rt)
            relative_deadline_s = self._relative_deadline_for_type(rt)
            absolute_deadline = current_time + relative_deadline_s

            req = Request(
                request_id=self.next_request_id,
                request_type=rt,
                source_position=(x, y),
                arrival_time=current_time,
                processing_demand=proc_cost,
                remaining_demand=proc_cost,
                data_size=data_size,
                latency_slo=latency_slo,
                is_emergency=is_emergency,
                priority_class=priority_class,
                relative_deadline_s=relative_deadline_s,
                absolute_deadline=absolute_deadline,
            )
            self.next_request_id += 1
            requests.append(req)

        return requests
