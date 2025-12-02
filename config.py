# config.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class SimulationConfig:
    """
    Holds all tunable parameters for the simulator.
    You can change these values directly or pass overrides from main.py.
    """
    # Time settings
    sim_time: float = 3600.0      # total simulation time in seconds
    time_step: float = 1.0        # length of each time step in seconds
    # Optional: if specified, the simulator will use this many
    # milliseconds per time step (i.e. dt = time_step_ms / 1000.0)
    # When `time_step_ms` is not None, it takes precedence over `time_step`.
    time_step_ms: Optional[int] = None

    # Random seed for reproducibility
    random_seed: int = 42

    # City / area where edge users and fog nodes live
    city_width: float = 1000.0    # meters (arbitrary)
    city_height: float = 1000.0   # meters

    # Fog topology: grid of fog nodes
    num_fog_nodes_x: int = 2      # number of fog nodes along x
    num_fog_nodes_y: int = 2      # number of fog nodes along y

    # Fog node resources
    fog_cpu_capacity: float = 10.0    # CPU units per second (will be scaled by dt)
    fog_link_capacity: float = 50.0   # MB per second per fog node (will be scaled by dt)
    # Optional per-node queue limit (None means unbounded)
    fog_max_queue_length: Optional[int] = None

    # Workload generation
    avg_requests_per_step: float = 5.0   # approximate average requests per time step (Poisson-like)
    max_requests_per_step: int = 200     # upper bound used to approximate Poisson with Bernoulli trials (increased for high-load scenarios)

    # Scheduler configuration
    scheduler: str = "FIFO"              # "FIFO", "EMERGENCY_FIRST", "STATIC_PRIORITY", or "SLA-DWP-Fog"

    # SLA-DWP-Fog settings (time-based window, thresholds, step sizes)
    # Window length in seconds for SLA monitoring
    sla_window_TW: float = 10.0
    # SLA thresholds: J1 (emergency miss ratio), J2 (mean latency seconds), J3 (fairness ratio)
    sla_J1_max: float = 0.10
    sla_J2_max_s: float = 5.0
    sla_J3_max: float = 2.0
    # Dual variable step sizes (>=0)
    sla_eta1: float = 0.01
    sla_eta2: float = 0.01
    sla_eta3: float = 0.01
    # Numerical safety epsilon for weight normalization
    sla_eps: float = 1e-6
