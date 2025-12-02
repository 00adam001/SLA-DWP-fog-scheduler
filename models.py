# models.py
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple


class RequestType(Enum):
    """
    Types of user-generated service requests at the edge,
    based on the professor's list.
    """
    LANE_GUIDANCE = auto()                # Lane-level guidance (AR overlays)
    NAVIGATION_REROUTING = auto()         # Real-time navigation / re-routing
    PARKING_DISCOVERY = auto()            # Parking discovery & reservation
    EV_CHARGER_BOOKING = auto()           # EV charger find & book
    TOLLING_CHARGING = auto()             # Tolling / road-use charging
    EMERGENCY_SOS = auto()                # Emergency SOS
    INCIDENT_UPLOAD = auto()              # Incident upload (e.g., photos/video)
    COLLISION_ALERT = auto()              # Forward-collision / pedestrian alert
    SPEED_LIMIT_AR = auto()               # Speed-limit / sign recognition (AR)
    ROAD_HAZARD_BROADCAST = auto()        # Road-hazard broadcast (V2X)
    DROWSINESS_ALERT = auto()             # Driver drowsiness / distraction alert
    SURROUND_VIEW = auto()                # Surround-view / blind-spot assist
    SCHOOL_ZONE_ADVISORY = auto()         # School / construction zone advisory
    WEATHER_AWARE_ROUTING = auto()        # Weather-aware routing (micro-forecasts)
    TRIP_SUMMARY_ANALYTICS = auto()       # Trip summary & usage analytics


@dataclass
class Request:
    """
    A single service request generated at the edge and handled by a fog node.
    """
    request_id: int
    request_type: RequestType
    source_position: Tuple[float, float]  # (x, y) in city coordinates
    arrival_time: float                   # when request is generated

    # Resource and QoS attributes
    processing_demand: float              # CPU units required in total
    remaining_demand: float               # CPU units remaining to finish
    data_size: float                      # MB to send over link
    is_emergency: bool = False            # True if emergency-type request
    latency_slo: Optional[float] = None   # soft deadline (seconds), optional

    # QoS and Priority fields (for deadline-aware scheduling)
    priority_class: int = 1               # 3=Emergency, 2=Safety-critical, 1=Non-critical
    relative_deadline_s: float = 60.0     # Target max end-to-end latency (seconds)
    absolute_deadline: float = 0.0        # arrival_time + relative_deadline_s

    # Runtime fields (filled during simulation)
    assigned_fog_id: Optional[int] = None
    start_time: Optional[float] = None
    completion_time: Optional[float] = None

    def latency(self) -> Optional[float]:
        """Return end-to-end latency (completion - arrival) if completed."""
        if self.completion_time is None:
            return None
        return self.completion_time - self.arrival_time

    def deadline_met(self) -> Optional[bool]:
        """Return True if completed within deadline, False if violated, None if not completed."""
        if self.completion_time is None:
            return None
        return self.completion_time <= self.absolute_deadline
