# System Architecture

## Overview

This document describes the complete architecture of the **SLA-Aware Dynamic Weighted Priority Scheduling for Fog Computing** simulation framework.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Simulation Framework                      │
│                                                              │
│  ┌────────────────┐      ┌─────────────────┐               │
│  │   Config.py    │─────>│  Simulation.py  │               │
│  │  Parameters    │      │   Main Loop     │               │
│  └────────────────┘      └────────┬────────┘               │
│                                   │                          │
│                    ┌──────────────┼──────────────┐          │
│                    │              │              │          │
│         ┌──────────▼────┐  ┌─────▼──────┐  ┌───▼─────┐    │
│         │   Request      │  │  Topology  │  │ Metrics │    │
│         │  Generator     │  │  (Fog      │  │Collector│    │
│         │  (Poisson)     │  │   Nodes)   │  │         │    │
│         └────────────────┘  └────────────┘  └─────────┘    │
│                                   │                          │
│                          ┌────────▼────────┐                │
│                          │   Schedulers    │                │
│                          │  - FIFO         │                │
│                          │  - EMERGENCY    │                │
│                          │  - STATIC       │                │
│                          │  - SLA-DWP-Fog  │                │
│                          └─────────────────┘                │
└─────────────────────────────────────────────────────────────┘

        ▼                    ▼                    ▼
   ┌─────────┐         ┌─────────┐         ┌──────────┐
   │  Plots  │         │  JSON   │         │   PPT    │
   │  (PNG)  │         │  Data   │         │  Report  │
   └─────────┘         └─────────┘         └──────────┘
```

---

## Component Architecture

### 1. Configuration Layer (`config.py`)

**Purpose**: Centralized parameter management

**Class**: `SimulationConfig`

**Responsibilities**:
- System resources (CPU, link capacity, queue limits)
- Workload parameters (arrival rate, simulation time)
- Scheduler selection
- SLA-DWP-Fog parameters (TW, J_max, η, ε)

**Key Parameters**:
```python
@dataclass
class SimulationConfig:
    # Time settings
    sim_time: float = 3600.0
    time_step: float = 1.0
    
    # Topology
    num_fog_nodes_x: int = 2
    num_fog_nodes_y: int = 2
    city_width: float = 1000.0
    city_height: float = 1000.0
    
    # Resources
    fog_cpu_capacity: float = 20.0
    fog_link_capacity: float = 200.0
    fog_max_queue_length: Optional[int] = 300
    
    # Workload
    avg_requests_per_step: float = 5.0
    max_requests_per_step: int = 200
    
    # Scheduler
    scheduler: str = "SLA-DWP-Fog"
    
    # SLA-DWP-Fog settings
    sla_window_TW: float = 10.0
    sla_J1_max: float = 0.10
    sla_J2_max_s: float = 5.0
    sla_J3_max: float = 2.0
    sla_eta1: float = 0.02
    sla_eta2: float = 0.02
    sla_eta3: float = 0.02
    sla_eps: float = 1e-6
```

**Data Flow**:
```
config.py → simulation.py → topology.py → FogNode instances
         → request_generator.py
```

---

### 2. Data Models Layer (`models.py`)

**Purpose**: Define core data structures

**Classes**:

#### `RequestType` (Enum)
```python
class RequestType(Enum):
    VIDEO_STREAMING = "video_streaming"           # Priority 3 (Emergency)
    AUTONOMOUS_NAVIGATION = "autonomous_nav"      # Priority 2 (Safety)
    TRAFFIC_MONITORING = "traffic_monitoring"     # Priority 2 (Safety)
    PARKING_INFORMATION = "parking_info"          # Priority 1 (Normal)
    WEATHER_UPDATE = "weather_update"             # Priority 1 (Normal)
```

#### `Request` (Class)
```python
class Request:
    request_id: int
    request_type: RequestType
    user_position: Tuple[float, float]
    arrival_time: float
    data_size: float                    # MB
    processing_demand: float            # CPU units
    relative_deadline_s: float          # seconds
    absolute_deadline: float            # arrival_time + relative_deadline_s
    priority_class: int                 # 1=Normal, 2=Safety, 3=Emergency
    is_emergency: bool
    
    # Runtime state
    start_time: Optional[float]
    completion_time: Optional[float]
    remaining_demand: float
    
    # Methods
    def latency(self) -> Optional[float]
    def deadline_met(self) -> bool
```

**Request Type Specifications**:

| Type | Priority | Deadline (s) | Data (MB) | CPU (units) |
|------|----------|--------------|-----------|-------------|
| Video Streaming | 3 | 0.8-1.5 | 2.0-3.5 | 3.0-5.0 |
| Autonomous Nav | 2 | 0.8-1.5 | 2.0-3.5 | 3.0-5.0 |
| Traffic Monitor | 2 | 1.0-2.0 | 1.0-2.0 | 2.0-4.0 |
| Parking Info | 1 | 3.0-5.0 | 0.5-1.0 | 1.0-2.0 |
| Weather Update | 1 | 8.0-12.0 | 0.3-0.6 | 0.5-1.0 |

---

### 3. Request Generation Layer (`request_generator.py`)

**Purpose**: Generate synthetic workload with Poisson arrivals

**Class**: `RequestGenerator`

**Algorithm**:
```python
class RequestGenerator:
    def generate_requests(self, current_time: float, time_step: float) -> List[Request]:
        """
        Generate requests for current time step using Poisson approximation.
        
        Approach: Bernoulli trials (each with p = λ/n)
        where λ = avg_requests_per_step, n = max_requests_per_step
        """
        p = self.avg_requests_per_step / self.max_requests_per_step
        num_generated = sum(1 for _ in range(self.max_requests_per_step) 
                          if random.random() < p)
        
        requests = []
        for _ in range(num_generated):
            req_type = self._choose_request_type()  # Weighted random selection
            req = self._create_request(req_type, current_time)
            requests.append(req)
        
        return requests
```

**Request Type Distribution**:
- 30% Emergency (Video Streaming)
- 40% Safety-Critical (35% Autonomous, 5% Traffic)
- 30% Non-Critical (25% Parking, 5% Weather)

**Spatial Distribution**:
- Uniform random over city area [0, city_width] × [0, city_height]

---

### 4. Topology Layer (`topology.py`)

**Purpose**: Model fog infrastructure and routing

**Classes**:

#### `FogNode`
**Responsibilities**:
- Task queueing (3 priority queues for SLA-DWP-Fog)
- Scheduling logic (FIFO / EMERGENCY_FIRST / STATIC_PRIORITY / SLA-DWP-Fog)
- Admission control
- CPU/link resource management
- SLA weight adaptation

**State Variables**:
```python
# Resources
cpu_capacity: float
link_capacity: float
max_queue_length: Optional[int]

# Queues (SLA-DWP-Fog)
dynamic_queue_3: Deque[Request]  # Emergency
dynamic_queue_2: Deque[Request]  # Safety
dynamic_queue_1: Deque[Request]  # Normal
current_request: Optional[Request]

# SLA-DWP-Fog state
alpha: float  # Class importance weight
beta: float   # Deadline urgency weight
gamma: float  # Waiting time weight
lambda_1: float  # Emergency SLA dual
lambda_2: float  # Latency SLA dual
lambda_3: float  # Fairness SLA dual
_completed_history: List[Request]
_last_window_update: float
```

**Key Methods**:
```python
def enqueue_request(request, time_step) -> (bool, Optional[str])
def process_one_step(current_time, time_step) -> List[Request]
def _admission_control_check_timebased(request) -> bool
def _priority_score(request, current_time) -> float
def _select_next_request_sla(current_time) -> Optional[Request]
def _update_sla_weights_window(current_time) -> None
```

#### `FogTopology`
**Responsibilities**:
- Manage collection of fog nodes
- Route requests to nearest fog node (Euclidean distance)

**Routing Algorithm**:
```python
def get_nearest_fog(self, position: Tuple[float, float]) -> FogNode:
    """Find closest fog node to user position."""
    best_node = None
    best_dist = float("inf")
    
    for node in self.fog_nodes:
        dx = node.position[0] - position[0]
        dy = node.position[1] - position[1]
        dist = sqrt(dx * dx + dy * dy)
        
        if dist < best_dist:
            best_dist = dist
            best_node = node
    
    return best_node
```

**Topology Construction**:
```python
def build_grid_topology(config: SimulationConfig) -> FogTopology:
    """
    Build 2D grid of fog nodes.
    
    Grid: num_fog_nodes_x × num_fog_nodes_y
    Spacing: Evenly distributed over city area
    """
    fog_nodes = []
    step_x = config.city_width / (config.num_fog_nodes_x + 1)
    step_y = config.city_height / (config.num_fog_nodes_y + 1)
    
    for ix in range(config.num_fog_nodes_x):
        for iy in range(config.num_fog_nodes_y):
            x = (ix + 1) * step_x
            y = (iy + 1) * step_y
            node = FogNode(
                node_id=len(fog_nodes),
                position=(x, y),
                cpu_capacity=config.fog_cpu_capacity,
                link_capacity=config.fog_link_capacity,
                max_queue_length=config.fog_max_queue_length,
                scheduler=config.scheduler
            )
            # Wire SLA parameters
            for attr in ["sla_window_TW", "sla_J1_max", ...]:
                if hasattr(config, attr):
                    setattr(node, attr, getattr(config, attr))
            fog_nodes.append(node)
    
    return FogTopology(fog_nodes)
```

---

### 5. Simulation Engine Layer (`simulation.py`)

**Purpose**: Discrete-event simulation loop

**Class**: `Simulation`

**Main Loop**:
```python
def run(self) -> Dict[str, Any]:
    """
    Execute time-stepped simulation.
    
    Flow:
    1. Generate requests (Poisson arrivals)
    2. Route requests to nearest fog node
    3. Enqueue with admission control
    4. Process requests (scheduling)
    5. Collect metrics
    6. Advance time
    7. Repeat
    """
    current_time = 0.0
    
    while current_time < self.config.sim_time:
        # Step 1: Generate arrivals
        new_requests = self.request_generator.generate_requests(
            current_time, self.config.time_step
        )
        self.metrics.record_generated(new_requests)
        
        # Step 2: Route and enqueue
        for request in new_requests:
            fog_node = self.topology.get_nearest_fog(request.user_position)
            
            # Step 3: Admission control
            admitted, reason = fog_node.enqueue_request(
                request, self.config.time_step
            )
            
            if admitted:
                self.metrics.record_admitted(request)
            elif reason == "admission_rejected":
                self.metrics.record_rejected(request)
            else:  # queue_full
                self.metrics.record_dropped(request, reason)
        
        # Step 4: Process tasks at each fog node
        for node in self.topology.all_nodes():
            completed = node.process_one_step(current_time, self.config.time_step)
            self.metrics.record_completed(completed)
        
        # Step 5: Collect per-step metrics
        self.metrics.finalize_step(self.topology.all_nodes())
        
        # Step 6: Advance time
        current_time += self.config.time_step
    
    # Generate final report
    return self.metrics.final_report()
```

---

### 6. Metrics Collection Layer (`metrics.py`)

**Purpose**: Track and compute performance metrics

**Class**: `MetricsCollector`

**Tracked Metrics**:

**Counters**:
```python
total_generated: int
total_admitted: int
total_rejected: int  # Admission control rejections
total_dropped: int   # Queue full rejections
total_completed: int
```

**Per-Class Metrics**:
```python
# Priority class 3 (Emergency)
priority3_deadline_met: int
priority3_deadline_violated: int

# Priority class 2 (Safety-Critical)
priority2_deadline_met: int
priority2_deadline_violated: int

# Priority class 1 (Non-Critical)
priority1_deadline_met: int
priority1_deadline_violated: int
```

**Latency Tracking**:
```python
latencies: List[float]
emergency_latencies: List[float]
normal_latencies: List[float]
waiting_times_emergency: List[float]
waiting_times_safety: List[float]
waiting_times_normal: List[float]
```

**Time-Series**:
```python
per_step_generated: List[int]
per_step_completed: List[int]
per_step_dropped: List[int]
avg_queue_lengths: List[float]
max_queue_lengths: List[int]
```

**Computed Metrics**:
```python
def final_report(self) -> Dict[str, Any]:
    return {
        "total_generated": self.total_generated,
        "total_admitted": self.total_admitted,
        "total_rejected": self.total_rejected,
        "total_dropped": self.total_dropped,
        "total_completed": self.total_completed,
        
        "admission_rate": self.total_admitted / max(1, self.total_generated),
        "completion_rate": self.total_completed / max(1, self.total_generated),
        
        "deadline_miss_rate": self.total_deadline_violated / max(1, total_with_deadlines),
        
        "emergency_sla_met_rate": self.priority3_deadline_met / max(1, total_emergency),
        
        "mean_latency": statistics.mean(self.latencies) if self.latencies else 0.0,
        "p95_latency": np.percentile(self.latencies, 95) if self.latencies else 0.0,
        
        # Per-class rates, time series, etc.
    }
```

---

## Scheduler Comparison

### Scheduler Implementations

All four schedulers implemented in `FogNode.process_one_step()`:

#### 1. FIFO
```python
# Single queue, process in arrival order
while self.queue and capacity_left > 0:
    req = self.queue[0]
    # Process or partial process
    # ...
```

#### 2. EMERGENCY_FIRST
```python
# Two queues: emergency first, then normal
while self.emergency_queue and capacity_left > 0:
    # Process emergency
while self.normal_queue and capacity_left > 0:
    # Process normal
```

#### 3. STATIC_PRIORITY
```python
# Three queues: priority 3 → 2 → 1
for queue in [priority_queue_3, priority_queue_2, priority_queue_1]:
    while queue and capacity_left > 0:
        # Process in priority order
```

#### 4. SLA-DWP-Fog
```python
# Dynamic priority with adaptive weights
while capacity_left > 0:
    next_req = _select_next_request_sla(current_time)  # argmax π_i(t)
    # Process highest-priority request
    # Update SLA weights every TW seconds
```

---

## Data Flow Diagram

### Request Lifecycle

```
1. Generation
   RequestGenerator.generate_requests()
   ↓
2. Routing
   FogTopology.get_nearest_fog()
   ↓
3. Admission Control
   FogNode.enqueue_request()
   ├─ Pass: → Priority Queue (dynamic_queue_1/2/3)
   └─ Fail: → Metrics (rejected/dropped)
   ↓
4. Scheduling
   FogNode.process_one_step()
   ├─ Select: _select_next_request_sla()
   └─ Process: Allocate CPU capacity
   ↓
5. Completion
   Request.completion_time set
   ↓
6. Metrics Collection
   MetricsCollector.record_completed()
   ├─ Latency tracking
   ├─ Deadline checking
   └─ SLA metrics
   ↓
7. SLA Adaptation (every TW seconds)
   FogNode._update_sla_weights_window()
   ├─ Compute J1, J2, J3
   ├─ Update λ1, λ2, λ3
   └─ Normalize to α, β, γ
```

---

## File Organization

```
Project-Rework/
├── config.py                    # Configuration parameters
├── models.py                    # Data structures (Request, RequestType)
├── request_generator.py         # Workload generation
├── topology.py                  # FogNode, FogTopology, schedulers
├── simulation.py                # Main simulation loop
├── metrics.py                   # Performance tracking
├── main.py                      # Entry point
│
├── generate_comparison_plots.py      # 5 main comparison figures
├── generate_extended_plots.py        # 6 extended analysis figures
├── generate_detailed_presentation.py # PowerPoint generation
│
├── docs/
│   ├── SLA_DWP_Fog_Algorithm.md     # Algorithm documentation
│   ├── System_Architecture.md        # This file
│   └── ...
│
├── plots/
│   ├── COMPARISON/
│   │   ├── fig1_deadline_miss.png
│   │   ├── fig5_admission_rate.png
│   │   └── comparison_results.json
│   └── extended/
│       └── ...
│
└── Detailed_SLA_DWP_Fog_Presentation.pptx
```

---

## Deployment Architecture

### Local Execution
```
User → Python 3.11.9 → Simulation → Results (JSON/PNG/PPTX)
```

### Scalability Considerations

**Current Limitations**:
- Single-threaded execution
- In-memory data structures
- Limited to ~10,000 requests per simulation

**Potential Improvements**:
1. **Parallel Simulation**: Process fog nodes in parallel
2. **Distributed Computing**: Distribute load across machines
3. **Streaming Processing**: Handle arrivals in real-time
4. **GPU Acceleration**: Offload priority calculations to GPU

---

## Extension Points

### Adding New Schedulers

1. Add scheduler name to `config.py`:
```python
scheduler: str = "MY_NEW_SCHEDULER"
```

2. Implement in `FogNode.process_one_step()`:
```python
if self.scheduler == "MY_NEW_SCHEDULER":
    # Your scheduling logic
    pass
```

3. Update metrics tracking if needed

### Adding New Request Types

1. Add to `RequestType` enum in `models.py`
2. Update `RequestGenerator._choose_request_type()`
3. Update `RequestGenerator._create_request()`

### Adding New Metrics

1. Add tracking variables to `MetricsCollector.__init__()`
2. Implement `record_*()` methods
3. Add to `final_report()` output

---

## Performance Optimization

### Current Bottlenecks

1. **Selection Phase**: O(n) per dequeue in SLA-DWP-Fog
   - **Solution**: Use priority heap with dynamic key updates

2. **SLA Metrics**: O(m) every TW seconds
   - **Solution**: Incremental metric updates

3. **Queue Management**: O(n) for removal from deque
   - **Solution**: Use indexed data structures

### Memory Usage

**Estimated per simulation**:
- Requests: ~200 KB per 1000 requests
- Metrics history: ~500 KB for 3600-second simulation
- Total: < 10 MB for typical runs

---

## Testing Strategy

### Unit Tests
- Request generation (Poisson distribution validation)
- Admission control (deadline prediction accuracy)
- Priority scoring (component bounds verification)
- SLA metrics (J1, J2, J3 computation)

### Integration Tests
- Full simulation with all schedulers
- Metric consistency across runs
- Configuration propagation

### Validation Tests
- Admission rate: 1.0 at light load → 0.0 at heavy load
- SLA-DWP-Fog: 0% deadline violations at moderate load
- Latency trends: Increasing with load

---

## Error Handling

### Admission Failures
```python
(admitted, reason) = fog_node.enqueue_request(request, time_step)

if not admitted:
    if reason == "queue_full":
        metrics.record_dropped(request, reason)
    elif reason == "admission_rejected":
        metrics.record_rejected(request)
```

### Resource Constraints
- Queue capacity enforced before admission
- CPU capacity allocated per time step
- Link capacity checked (optional)

### Edge Cases
- Empty queues: Return None from selection
- Zero deadlines: Use ε = 1e-9 for numerical stability
- Division by zero: Max(1, denominator) patterns

---

## Version Control

**Current Version**: 1.0  
**Last Updated**: December 2025  
**Status**: Production

**Change Log**:
- v1.0: Initial release with SLA-DWP-Fog implementation
- v0.9: Added extended plotting and presentation generation
- v0.8: Implemented time-based admission control
- v0.7: Added dual-variable weight adaptation

---

## References

- **Simulation Framework**: Python discrete-event simulation
- **Fog Computing**: Edge computing paradigm for low-latency services
- **V2X Applications**: Vehicle-to-everything communication
- **Lagrangian Optimization**: Dual-based constraint handling

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Status**: Production
