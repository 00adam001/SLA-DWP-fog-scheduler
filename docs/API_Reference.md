# API Reference

## Overview

This document provides detailed API documentation for all public classes, methods, and functions in the SLA-DWP-Fog simulation framework.

---

## Module: `config.py`

### Class: `SimulationConfig`

**Description**: Dataclass holding all simulation parameters.

**Attributes**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `sim_time` | `float` | 3600.0 | Total simulation time (seconds) |
| `time_step` | `float` | 1.0 | Length of each time step (seconds) |
| `time_step_ms` | `Optional[int]` | None | Time step in milliseconds (overrides time_step if set) |
| `random_seed` | `int` | 42 | Random seed for reproducibility |
| `city_width` | `float` | 1000.0 | City area width (meters) |
| `city_height` | `float` | 1000.0 | City area height (meters) |
| `num_fog_nodes_x` | `int` | 2 | Number of fog nodes along x-axis |
| `num_fog_nodes_y` | `int` | 2 | Number of fog nodes along y-axis |
| `fog_cpu_capacity` | `float` | 10.0 | CPU units per second per node |
| `fog_link_capacity` | `float` | 50.0 | MB per second per node |
| `fog_max_queue_length` | `Optional[int]` | None | Maximum queue size (None = unbounded) |
| `avg_requests_per_step` | `float` | 5.0 | Average requests per time step |
| `max_requests_per_step` | `int` | 200 | Upper bound for Poisson approximation |
| `scheduler` | `str` | "FIFO" | Scheduler type: FIFO, EMERGENCY_FIRST, STATIC_PRIORITY, SLA-DWP-Fog |
| `sla_window_TW` | `float` | 10.0 | SLA monitoring time window (seconds) |
| `sla_J1_max` | `float` | 0.10 | Max emergency deadline miss ratio |
| `sla_J2_max_s` | `float` | 5.0 | Max mean latency (seconds) |
| `sla_J3_max` | `float` | 2.0 | Max fairness ratio |
| `sla_eta1` | `float` | 0.01 | Emergency SLA dual step size |
| `sla_eta2` | `float` | 0.01 | Latency SLA dual step size |
| `sla_eta3` | `float` | 0.01 | Fairness SLA dual step size |
| `sla_eps` | `float` | 1e-6 | Numerical stability epsilon |

**Example**:
```python
from config import SimulationConfig

config = SimulationConfig(
    sim_time=7200.0,
    scheduler="SLA-DWP-Fog",
    fog_cpu_capacity=40.0
)
```

---

## Module: `models.py`

### Enum: `RequestType`

**Description**: Enumeration of all request types.

**Values**:
- `VIDEO_STREAMING`: Video streaming service (Emergency, priority 3)
- `AUTONOMOUS_NAVIGATION`: Autonomous vehicle navigation (Safety, priority 2)
- `TRAFFIC_MONITORING`: Traffic monitoring (Safety, priority 2)
- `PARKING_INFORMATION`: Parking info service (Normal, priority 1)
- `WEATHER_UPDATE`: Weather update service (Normal, priority 1)

### Class: `Request`

**Description**: Represents a single task request.

**Constructor**:
```python
Request(
    request_id: int,
    request_type: RequestType,
    user_position: Tuple[float, float],
    arrival_time: float,
    data_size: float,
    processing_demand: float,
    relative_deadline_s: float,
    priority_class: int,
    is_emergency: bool
)
```

**Attributes**:

| Name | Type | Description |
|------|------|-------------|
| `request_id` | `int` | Unique identifier |
| `request_type` | `RequestType` | Type of request |
| `user_position` | `Tuple[float, float]` | (x, y) position in city |
| `arrival_time` | `float` | Arrival timestamp |
| `data_size` | `float` | Data size in MB |
| `processing_demand` | `float` | CPU units required |
| `relative_deadline_s` | `float` | Deadline relative to arrival (seconds) |
| `absolute_deadline` | `float` | arrival_time + relative_deadline_s |
| `priority_class` | `int` | 1=Normal, 2=Safety, 3=Emergency |
| `is_emergency` | `bool` | True if priority_class == 3 |
| `start_time` | `Optional[float]` | Processing start time (set by scheduler) |
| `completion_time` | `Optional[float]` | Completion time (set by scheduler) |
| `remaining_demand` | `float` | CPU units remaining (initialized to processing_demand) |

**Methods**:

#### `latency() -> Optional[float]`

Calculate end-to-end latency.

**Returns**: `completion_time - arrival_time` if completed, else `None`

**Example**:
```python
if request.completion_time is not None:
    lat = request.latency()
    print(f"Latency: {lat:.2f}s")
```

#### `deadline_met() -> bool`

Check if deadline was met.

**Returns**: `True` if `completion_time <= absolute_deadline`, else `False`

**Example**:
```python
if request.deadline_met():
    print("On time!")
else:
    print("Late!")
```

---

## Module: `request_generator.py`

### Class: `RequestGenerator`

**Description**: Generates synthetic workload with Poisson arrivals.

**Constructor**:
```python
RequestGenerator(
    avg_requests_per_step: float,
    max_requests_per_step: int,
    city_width: float,
    city_height: float
)
```

**Methods**:

#### `generate_requests(current_time: float, time_step: float) -> List[Request]`

Generate requests for current time step.

**Parameters**:
- `current_time`: Current simulation time
- `time_step`: Duration of this time step

**Returns**: List of generated `Request` objects

**Algorithm**: Poisson approximation via Bernoulli trials

**Example**:
```python
gen = RequestGenerator(avg_requests_per_step=5.0, max_requests_per_step=200,
                       city_width=1000.0, city_height=1000.0)

requests = gen.generate_requests(current_time=0.0, time_step=1.0)
print(f"Generated {len(requests)} requests")
```

---

## Module: `topology.py`

### Class: `FogNode`

**Description**: Represents a single fog node with scheduling logic.

**Constructor**:
```python
FogNode(
    node_id: int,
    position: Tuple[float, float],
    cpu_capacity: float,
    link_capacity: Optional[float] = None,
    max_queue_length: Optional[int] = None,
    scheduler: str = "FIFO"
)
```

**Methods**:

#### `reset_step_state() -> None`

Reset per-step state (link load).

**Called**: Before processing new arrivals each step

#### `can_accept_request(request: Request, time_step: float) -> bool`

Check if link capacity can handle request.

**Returns**: `True` if sufficient link capacity, else `False`

#### `enqueue_request(request: Request, time_step: float) -> Tuple[bool, Optional[str]]`

Attempt to enqueue request with admission control.

**Parameters**:
- `request`: Incoming request
- `time_step`: Current time step duration

**Returns**:
- `(True, None)`: Request admitted
- `(False, "queue_full")`: Queue at capacity
- `(False, "admission_rejected")`: Failed admission control (SLA-DWP-Fog only)

**Example**:
```python
admitted, reason = fog_node.enqueue_request(request, time_step=1.0)

if admitted:
    print("Request accepted")
elif reason == "admission_rejected":
    print("Rejected by admission control")
else:  # queue_full
    print("Queue full")
```

#### `process_one_step(current_time: float, time_step: float) -> List[Request]`

Process requests for one time step according to scheduler.

**Parameters**:
- `current_time`: Current simulation time
- `time_step`: Duration of this time step

**Returns**: List of completed requests

**Example**:
```python
completed = fog_node.process_one_step(current_time=10.0, time_step=1.0)
print(f"Completed {len(completed)} requests this step")
```

#### `queue_length() -> int`

Get total queue length across all queues.

**Returns**: Number of queued requests (excludes currently processing)

#### `_admission_control_check_timebased(request: Request) -> bool`

**SLA-DWP-Fog only**: Check if request can meet deadline.

**Returns**: `True` if predicted finish ≤ deadline, else `False`

**Internal**: Called by `enqueue_request()`

#### `_priority_score(request: Request, current_time: float) -> float`

**SLA-DWP-Fog only**: Compute priority score π_i(t).

**Returns**: Score in [0, 1]

**Formula**: `α·g(κ) + β·u(t) + γ·w(t)`

#### `_select_next_request_sla(current_time: float) -> Optional[Request]`

**SLA-DWP-Fog only**: Select highest-priority request.

**Returns**: Request with max π_i(t), or `None` if queues empty

#### `_update_sla_weights_window(current_time: float) -> None`

**SLA-DWP-Fog only**: Update α, β, γ based on SLA metrics.

**Called**: Every `sla_window_TW` seconds

**Effect**: Adjusts dual variables λ₁, λ₂, λ₃ and normalizes to weights

### Class: `FogTopology`

**Description**: Manages collection of fog nodes.

**Constructor**:
```python
FogTopology(fog_nodes: List[FogNode])
```

**Methods**:

#### `all_nodes() -> List[FogNode]`

Get all fog nodes.

**Returns**: List of `FogNode` objects

#### `get_nearest_fog(position: Tuple[float, float]) -> FogNode`

Find closest fog node to user position.

**Parameters**:
- `position`: (x, y) user coordinates

**Returns**: Nearest `FogNode` (Euclidean distance)

**Example**:
```python
user_pos = (250.0, 750.0)
nearest = topology.get_nearest_fog(user_pos)
print(f"Routing to node {nearest.node_id}")
```

### Function: `build_grid_topology(config: SimulationConfig) -> FogTopology`

Construct grid of fog nodes.

**Parameters**:
- `config`: Simulation configuration

**Returns**: `FogTopology` with num_fog_nodes_x × num_fog_nodes_y nodes

**Node Placement**: Evenly spaced grid over city area

**Example**:
```python
from topology import build_grid_topology
from config import SimulationConfig

config = SimulationConfig(num_fog_nodes_x=3, num_fog_nodes_y=3)
topology = build_grid_topology(config)  # 3×3 = 9 nodes
```

---

## Module: `simulation.py`

### Class: `Simulation`

**Description**: Main simulation engine.

**Constructor**:
```python
Simulation(config: SimulationConfig)
```

**Methods**:

#### `run() -> Dict[str, Any]`

Execute complete simulation.

**Returns**: Dictionary of final metrics

**Keys**:
- `total_generated`: int
- `total_admitted`: int
- `total_rejected`: int
- `total_dropped`: int
- `total_completed`: int
- `admission_rate`: float
- `completion_rate`: float
- `deadline_miss_rate`: float
- `emergency_sla_met_rate`: float
- `mean_latency`: float
- `p95_latency`: float
- Plus per-step arrays and other metrics

**Example**:
```python
from config import SimulationConfig
from simulation import Simulation

config = SimulationConfig(scheduler="SLA-DWP-Fog", avg_requests_per_step=30.0)
sim = Simulation(config)
results = sim.run()

print(f"Admission Rate: {results['admission_rate']:.2%}")
print(f"Deadline Miss Rate: {results['deadline_miss_rate']:.2%}")
```

---

## Module: `metrics.py`

### Class: `MetricsCollector`

**Description**: Tracks simulation statistics.

**Constructor**:
```python
MetricsCollector()
```

**Methods**:

#### `record_generated(requests: List[Request]) -> None`

Record newly generated requests.

**Parameters**:
- `requests`: List of generated requests

**Effect**: Increments `total_generated`, updates per-type and per-step counts

#### `record_admitted(request: Request) -> None`

Record request admitted to queue.

**Parameters**:
- `request`: Admitted request

**Effect**: Increments `total_admitted`

#### `record_rejected(request: Request) -> None`

Record request rejected by admission control.

**Parameters**:
- `request`: Rejected request

**Effect**: Increments `total_rejected`

#### `record_dropped(request: Request, reason: str) -> None`

Record request dropped due to queue full.

**Parameters**:
- `request`: Dropped request
- `reason`: Drop reason (e.g., "queue_full")

**Effect**: Increments `total_dropped`, updates per-type and reason breakdown

#### `record_completed(completed: List[Request]) -> None`

Record completed requests.

**Parameters**:
- `completed`: List of completed requests

**Effect**: Updates latencies, deadline stats, per-class metrics

#### `finalize_step(nodes: List[FogNode]) -> None`

Finalize per-step metrics.

**Parameters**:
- `nodes`: All fog nodes

**Effect**: Records queue lengths, completion counts

**Called**: End of each simulation time step

#### `final_report() -> Dict[str, Any]`

Generate final summary statistics.

**Returns**: Dictionary with all aggregated metrics

**Called**: End of simulation

**Example**:
```python
metrics = MetricsCollector()

# During simulation
metrics.record_generated(new_requests)
for req in new_requests:
    admitted, reason = fog_node.enqueue_request(req, time_step)
    if admitted:
        metrics.record_admitted(req)
    elif reason == "admission_rejected":
        metrics.record_rejected(req)
    else:
        metrics.record_dropped(req, reason)

completed = fog_node.process_one_step(current_time, time_step)
metrics.record_completed(completed)

# End of simulation
report = metrics.final_report()
```

---

## Visualization Functions

### Module: `generate_comparison_plots.py`

#### Function: `run_single_config(scheduler: str, load: float, config_base: SimulationConfig) -> Dict[str, Any]`

Run simulation with specific scheduler and load.

**Parameters**:
- `scheduler`: Scheduler name
- `load`: Requests per step
- `config_base`: Base configuration

**Returns**: Simulation results dictionary

#### Function: `plot_metric(loads, data_by_scheduler, metric_key, ylabel, title, filename, ylim=None)`

Generate line plot comparing schedulers.

**Parameters**:
- `loads`: List of load values (x-axis)
- `data_by_scheduler`: Nested dict {scheduler: {load: metrics}}
- `metric_key`: Metric to plot (e.g., "deadline_miss_rate")
- `ylabel`: Y-axis label
- `title`: Plot title
- `filename`: Output filename
- `ylim`: Optional y-axis limits

**Effect**: Saves PNG figure to `plots/COMPARISON/`

### Module: `generate_extended_plots.py`

#### Function: `plot_timeseries(results, load, output_path)`

Generate time-series plot of queue length and completions.

#### Function: `plot_per_class_latency(results, load, output_path)`

Generate boxplot of per-class latencies.

#### Function: `plot_cdf_latencies(results, load, output_path)`

Generate CDF of latencies.

#### Function: `plot_sla_compliance(data_by_load, output_path)`

Generate SLA compliance tracking plot (SLA-DWP-Fog only).

---

## Usage Patterns

### Pattern 1: Single Simulation Run

```python
from config import SimulationConfig
from simulation import Simulation

# Configure
config = SimulationConfig(
    scheduler="SLA-DWP-Fog",
    avg_requests_per_step=30.0,
    fog_cpu_capacity=20.0
)

# Run
sim = Simulation(config)
results = sim.run()

# Analyze
print(f"Admission: {results['admission_rate']:.2%}")
print(f"Violations: {results['deadline_miss_rate']:.2%}")
```

### Pattern 2: Scheduler Comparison

```python
schedulers = ["FIFO", "EMERGENCY_FIRST", "STATIC_PRIORITY", "SLA-DWP-Fog"]

for sched in schedulers:
    config = SimulationConfig(scheduler=sched, avg_requests_per_step=30.0)
    results = Simulation(config).run()
    print(f"{sched}: {results['deadline_miss_rate']:.4f}")
```

### Pattern 3: Load Sweep

```python
loads = [2, 10, 30, 60, 100]
admission_rates = []

for load in loads:
    config = SimulationConfig(scheduler="SLA-DWP-Fog", avg_requests_per_step=load)
    results = Simulation(config).run()
    admission_rates.append(results['admission_rate'])

# Plot
import matplotlib.pyplot as plt
plt.plot(loads, admission_rates, marker='o')
plt.xlabel('Load (req/step)')
plt.ylabel('Admission Rate')
plt.title('Admission Rate vs Load')
plt.savefig('admission_vs_load.png')
```

---

## Error Handling

### Common Exceptions

**ValueError**: Invalid configuration
```python
try:
    config = SimulationConfig(num_fog_nodes_x=-1)
except ValueError as e:
    print(f"Invalid config: {e}")
```

**AttributeError**: Missing SLA parameters for SLA-DWP-Fog
```python
# Automatically handled via getattr() with defaults
# No exception raised
```

**IndexError**: Empty queues
```python
# Handled internally in FogNode
# Methods return None or empty list
```

---

## Type Hints

All functions and methods include full type annotations:

```python
from typing import List, Dict, Tuple, Optional, Any

def process_one_step(
    self, 
    current_time: float, 
    time_step: float
) -> List[Request]:
    ...
```

Use with `mypy` for static type checking:
```powershell
pip install mypy
mypy simulation.py
```

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Status**: Production
