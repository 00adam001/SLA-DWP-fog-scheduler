# Scheduler Comparison Guide

## Overview

This document provides a detailed comparison of all four scheduling algorithms implemented in the fog computing simulation framework.

---

## Scheduler Summary Table

| Scheduler | Queue Strategy | Admission Control | Priority Mechanism | Complexity | Deadline Miss @ Load=30 |
|-----------|---------------|-------------------|-------------------|------------|------------------------|
| **FIFO** | Single queue | Queue limit only | None (arrival order) | O(1) | 84.82% |
| **EMERGENCY_FIRST** | 2 queues | Queue limit only | Binary (emergency vs normal) | O(1) | 92.96% |
| **STATIC_PRIORITY** | 3 queues | Queue limit only | Fixed class priority | O(1) | 92.96% |
| **SLA-DWP-Fog** | 3 queues | Time-based prediction | Dynamic adaptive | O(n) | 0.00% |

---

## 1. FIFO Scheduler

### Algorithm Description

**First-In-First-Out**: Process tasks in strict arrival order without any prioritization.

### Implementation

**Location**: `topology.py`, `FogNode.process_one_step()`

```python
def process_one_step(self, current_time: float, time_step: float) -> List[Request]:
    """FIFO mode: process single queue in arrival order."""
    completed = []
    capacity_left = self.cpu_capacity * time_step
    
    while self.queue and capacity_left > 0:
        req = self.queue[0]  # Always take first in queue
        
        if req.start_time is None:
            req.start_time = current_time
        
        if req.remaining_demand <= capacity_left:
            # Complete request
            capacity_left -= req.remaining_demand
            req.remaining_demand = 0.0
            req.completion_time = current_time + time_step
            completed.append(req)
            self.queue.popleft()
        else:
            # Partial processing
            req.remaining_demand -= capacity_left
            capacity_left = 0.0
    
    return completed
```

### Characteristics

**Strengths**:
- ✅ **Simplicity**: Minimal implementation complexity
- ✅ **Fairness**: Equal treatment based on arrival order
- ✅ **Predictability**: Deterministic behavior
- ✅ **Low overhead**: O(1) enqueue and dequeue operations

**Weaknesses**:
- ❌ **No QoS differentiation**: Emergency tasks wait like any other
- ❌ **High deadline violations**: 84.82% miss rate at load=30
- ❌ **Poor for real-time**: Cannot guarantee latency bounds
- ❌ **No admission control**: Accepts all until queue full

### Use Cases

- **Best for**: Non-critical batch processing, fair-share systems
- **Avoid for**: Real-time systems, mixed-priority workloads, safety-critical applications

### Performance Results

| Load | Admission Rate | Deadline Miss | Mean Latency (s) |
|------|---------------|---------------|------------------|
| 2 | 1.0000 | 0.0119 | 0.15 |
| 10 | 0.9903 | 0.3652 | 1.82 |
| 30 | 0.5115 | 0.8482 | 9.73 |
| 60 | 0.2158 | 0.9634 | 23.86 |
| 100 | 0.0419 | 0.9847 | 39.52 |

---

## 2. EMERGENCY_FIRST Scheduler

### Algorithm Description

**Binary Priority**: Maintain two separate queues (emergency and normal), always process emergency queue first.

### Implementation

```python
def process_one_step(self, current_time: float, time_step: float) -> List[Request]:
    """EMERGENCY_FIRST mode: process emergency queue first."""
    completed = []
    capacity_left = self.cpu_capacity * time_step
    
    # Phase 1: Process emergency queue
    while self.emergency_queue and capacity_left > 0:
        req = self.emergency_queue[0]
        
        if req.start_time is None:
            req.start_time = current_time
        
        if req.remaining_demand <= capacity_left:
            capacity_left -= req.remaining_demand
            req.remaining_demand = 0.0
            req.completion_time = current_time + time_step
            completed.append(req)
            self.emergency_queue.popleft()
        else:
            req.remaining_demand -= capacity_left
            capacity_left = 0.0
    
    # Phase 2: Process normal queue with remaining capacity
    while self.normal_queue and capacity_left > 0:
        req = self.normal_queue[0]
        # ... same processing logic
    
    return completed
```

### Queue Assignment

```python
def enqueue_request(self, request: Request, time_step: float):
    """Add to appropriate queue based on emergency status."""
    if request.is_emergency:
        self.emergency_queue.append(request)
    else:
        self.normal_queue.append(request)
```

**Emergency Classification**:
- `request.is_emergency = True` if `request.priority_class == 3`
- Includes: Video Streaming, critical safety applications

### Characteristics

**Strengths**:
- ✅ **Emergency protection**: Guarantees emergency tasks processed first
- ✅ **Simple implementation**: Only two queues
- ✅ **Low overhead**: O(1) operations

**Weaknesses**:
- ❌ **No differentiation within classes**: All emergencies treated equally
- ❌ **Starvation risk**: Normal tasks may wait indefinitely under heavy emergency load
- ❌ **High violations**: 92.96% miss rate (worse than FIFO!)
- ❌ **No admission control**: Still accepts all requests

### Why Worse Than FIFO?

**Paradox**: Emergency-first actually has *higher* deadline miss rate than FIFO at load=30.

**Explanation**:
1. Emergency tasks have **tighter deadlines** (0.8-1.5s)
2. Prioritizing them first causes **longer waits** for normal tasks
3. Normal tasks then miss their (longer) deadlines
4. Emergency tasks **also** miss deadlines due to queue buildup
5. Result: **Both** classes suffer from poor admission control

### Use Cases

- **Best for**: Systems with rare emergencies, low overall load
- **Avoid for**: Heavy mixed workloads, need for overall QoS guarantees

### Performance Results

| Load | Admission Rate | Deadline Miss | Emergency SLA Met |
|------|---------------|---------------|-------------------|
| 2 | 1.0000 | 0.0119 | 1.0000 |
| 10 | 0.9913 | 0.3902 | 0.9945 |
| 30 | 0.5212 | 0.9296 | 0.5152 |
| 60 | 0.2211 | 0.9841 | 0.0872 |
| 100 | 0.0376 | 0.9942 | 0.0109 |

---

## 3. STATIC_PRIORITY Scheduler

### Algorithm Description

**Three-Tier Priority**: Maintain three queues by priority class, process in strict order (3 → 2 → 1).

### Implementation

```python
def process_one_step(self, current_time: float, time_step: float) -> List[Request]:
    """STATIC_PRIORITY mode: process priority_queue_3 → 2 → 1."""
    completed = []
    capacity_left = self.cpu_capacity * time_step
    
    # Process in priority order
    for queue in [self.priority_queue_3, self.priority_queue_2, self.priority_queue_1]:
        while queue and capacity_left > 0:
            req = queue[0]
            
            if req.start_time is None:
                req.start_time = current_time
            
            if req.remaining_demand <= capacity_left:
                capacity_left -= req.remaining_demand
                req.remaining_demand = 0.0
                req.completion_time = current_time + time_step
                completed.append(req)
                queue.popleft()
            else:
                req.remaining_demand -= capacity_left
                capacity_left = 0.0
    
    return completed
```

### Queue Assignment

```python
def enqueue_request(self, request: Request, time_step: float):
    """Add to queue matching priority_class."""
    if request.priority_class == 3:      # Emergency
        self.priority_queue_3.append(request)
    elif request.priority_class == 2:    # Safety-Critical
        self.priority_queue_2.append(request)
    else:                                 # Non-Critical (class 1)
        self.priority_queue_1.append(request)
```

**Priority Classes**:
- **Class 3** (Emergency): Video Streaming
- **Class 2** (Safety-Critical): Autonomous Navigation, Traffic Monitoring
- **Class 1** (Non-Critical): Parking Info, Weather Updates

### Characteristics

**Strengths**:
- ✅ **Three-tier QoS**: Better differentiation than binary
- ✅ **Deterministic**: Predictable behavior per class
- ✅ **Simple**: Easy to understand and implement

**Weaknesses**:
- ❌ **No adaptability**: Cannot adjust to workload patterns
- ❌ **Starvation**: Class 1 tasks may never run under heavy 2/3 load
- ❌ **Same violations as EMERGENCY_FIRST**: 92.96% at load=30
- ❌ **Ignores deadlines**: No awareness of time constraints

### Comparison with EMERGENCY_FIRST

**Performance**: Nearly identical (both ~92.96% miss rate)

**Why?**
- Class 3 = Emergency in both
- Class 2+1 = Normal in EMERGENCY_FIRST
- Same fundamental issue: no admission control

### Use Cases

- **Best for**: Well-understood fixed workloads, three distinct SLA tiers
- **Avoid for**: Dynamic workloads, need for deadline guarantees

### Performance Results

| Load | Admission Rate | Deadline Miss | Class 3 SLA Met |
|------|---------------|---------------|-----------------|
| 2 | 1.0000 | 0.0119 | 1.0000 |
| 10 | 0.9913 | 0.3902 | 0.9945 |
| 30 | 0.5212 | 0.9296 | 0.5152 |
| 60 | 0.2211 | 0.9841 | 0.0872 |
| 100 | 0.0376 | 0.9942 | 0.0109 |

---

## 4. SLA-DWP-Fog Scheduler

### Algorithm Description

**Adaptive Weighted Priority with Admission Control**: Combines time-based admission prediction with dynamic priority scoring that adapts based on observed SLA violations.

### Implementation Overview

**Three Key Innovations**:
1. **Time-based admission control**: Reject tasks that cannot meet deadlines
2. **Normalized priority scoring**: π_i(t) = α·g(κ) + β·u(t) + γ·w(t)
3. **Dual-variable adaptation**: Weights α, β, γ adjust every 10 seconds

### Core Functions

See detailed documentation in `docs/SLA_DWP_Fog_Algorithm.md` for:
- `_admission_control_check_timebased()`
- `_priority_score()`
- `_select_next_request_sla()`
- `_update_sla_weights_window()`

### Characteristics

**Strengths**:
- ✅ **Zero deadline violations**: 0.00% at load=30 (vs 85-93% for others)
- ✅ **Adaptive behavior**: Adjusts to workload patterns automatically
- ✅ **Multi-objective**: Balances class priority, urgency, fairness
- ✅ **Proactive**: Prevents wasted work on tasks that will be late
- ✅ **Theoretical foundation**: Based on Lagrangian optimization

**Weaknesses**:
- ❌ **Lower admission**: 81.55% at load=2 (vs 100% for others)
- ❌ **Higher complexity**: O(n) selection vs O(1)
- ❌ **Parameter tuning**: Requires calibration of η, J_max
- ❌ **Adaptation delay**: 10-second window may be slow

### Trade-off Analysis

**SLA-DWP-Fog Philosophy**: "Better to reject early than complete late"

**Comparison at Load=2 (Light Load)**:
- FIFO: 100% admission, 1.19% violations
- SLA-DWP-Fog: 81.55% admission, **0% violations**

**Interpretation**: Even at light loads, SLA-DWP-Fog proactively rejects ~18% of tasks because predicted finish time exceeds deadline. This prevents violating SLA for completed tasks.

### Use Cases

- **Best for**: Safety-critical systems, strict SLA requirements, real-time applications
- **Avoid for**: Best-effort systems, maximum throughput goals, simple workloads

### Performance Results

| Load | Admission Rate | Deadline Miss | Emergency SLA Met |
|------|---------------|---------------|-------------------|
| 2 | 0.8155 | 0.0000 | 1.0000 |
| 10 | 0.8154 | 0.0000 | 1.0000 |
| 30 | 0.4299 | 0.0000 | 1.0000 |
| 60 | 0.1670 | 0.0000 | 1.0000 |
| 100 | 0.0368 | 0.0000 | 1.0000 |

**Key Insight**: Maintains 0% violations across entire load range by strategically rejecting tasks.

---

## Head-to-Head Comparison

### Scenario 1: Light Load (Load = 2)

| Scheduler | Admission | Violations | Latency (s) | Verdict |
|-----------|-----------|-----------|-------------|---------|
| FIFO | 100% | 1.19% | 0.15 | Good throughput, minor violations |
| EMERGENCY | 100% | 1.19% | 0.15 | Same as FIFO at light load |
| STATIC | 100% | 1.19% | 0.15 | Same as FIFO at light load |
| **SLA-DWP** | **81.55%** | **0%** | **0.18** | Perfect SLA, lower throughput |

**Winner**: Depends on goal
- **Max throughput**: FIFO (100% admission)
- **Zero violations**: SLA-DWP-Fog

### Scenario 2: Moderate Load (Load = 30)

| Scheduler | Admission | Violations | Emergency SLA | Verdict |
|-----------|-----------|-----------|---------------|---------|
| FIFO | 51.15% | 84.82% | 16.79% | Poor QoS |
| EMERGENCY | 52.12% | 92.96% | 51.52% | Worse than FIFO! |
| STATIC | 52.12% | 92.96% | 51.52% | Same as EMERGENCY |
| **SLA-DWP** | **42.99%** | **0%** | **100%** | Perfect QoS |

**Winner**: **SLA-DWP-Fog** (achieves SLA goals)

**Why others fail**:
- Accept all requests without checking feasibility
- Queue buildup causes massive delays
- Emergency tasks also suffer from congestion

### Scenario 3: Heavy Overload (Load = 100)

| Scheduler | Admission | Violations | Completion Ratio | Verdict |
|-----------|-----------|-----------|------------------|---------|
| FIFO | 4.19% | 98.47% | 0.0419 | System collapse |
| EMERGENCY | 3.76% | 99.42% | 0.0376 | Worse collapse |
| STATIC | 3.76% | 99.42% | 0.0376 | Worse collapse |
| **SLA-DWP** | **3.68%** | **0%** | **0.0368** | Controlled degradation |

**Winner**: **SLA-DWP-Fog** (maintains SLA even in overload)

**Key Difference**: All have similar admission (~3-4%), but SLA-DWP-Fog ensures admitted tasks complete on time.

---

## Algorithmic Complexity Comparison

| Operation | FIFO | EMERGENCY | STATIC | SLA-DWP |
|-----------|------|-----------|--------|---------|
| Enqueue | O(1) | O(1) | O(1) | O(n) - admission check |
| Dequeue | O(1) | O(1) | O(1) | O(n) - priority selection |
| Per-step | O(k) | O(k) | O(k) | O(n²) worst, O(kn) typical |
| Weight update | - | - | - | O(m) every TW seconds |

where:
- k = number of tasks processed this step (≤ CPU capacity)
- n = total queued tasks
- m = completed tasks in window TW

**Optimization Opportunity**: SLA-DWP-Fog could use priority heap to reduce selection to O(log n).

---

## Configuration Comparison

### FIFO Configuration
```python
config = SimulationConfig(
    scheduler="FIFO",
    fog_max_queue_length=300  # Only parameter needed
)
```

### SLA-DWP-Fog Configuration
```python
config = SimulationConfig(
    scheduler="SLA-DWP-Fog",
    fog_max_queue_length=300,
    sla_window_TW=10.0,        # 7 additional parameters
    sla_J1_max=0.10,
    sla_J2_max_s=5.0,
    sla_J3_max=2.0,
    sla_eta1=0.02,
    sla_eta2=0.02,
    sla_eta3=0.02,
    sla_eps=1e-6
)
```

**Complexity Trade-off**: SLA-DWP-Fog requires careful parameter tuning.

---

## When to Use Each Scheduler

### Use FIFO When:
- ✓ Workload is homogeneous (no priorities)
- ✓ Best-effort service is acceptable
- ✓ Simplicity is paramount
- ✓ Light load with minimal congestion

### Use EMERGENCY_FIRST When:
- ✓ Clear binary classification (critical vs non-critical)
- ✓ Emergency load is low (<20% of total)
- ✓ Simple priority is sufficient
- ✗ **Avoid at moderate-heavy loads** (worse than FIFO)

### Use STATIC_PRIORITY When:
- ✓ Fixed three-tier SLA structure
- ✓ Workload patterns are stable
- ✓ Deterministic behavior needed
- ✗ **Same limitations as EMERGENCY_FIRST**

### Use SLA-DWP-Fog When:
- ✓ **Strict deadline guarantees required**
- ✓ Safety-critical applications (V2X, healthcare)
- ✓ Mixed-priority workload with tight deadlines
- ✓ Willing to sacrifice admission for QoS compliance
- ✓ Can tune 7+ parameters
- ✓ Acceptable O(n) overhead

---

## Migration Guide

### Switching from FIFO to SLA-DWP-Fog

**Step 1**: Baseline metrics with FIFO
```bash
python main.py  # scheduler="FIFO"
# Record: admission_rate, deadline_miss_rate
```

**Step 2**: Enable SLA-DWP-Fog with default parameters
```python
config.scheduler = "SLA-DWP-Fog"
# Keep default SLA parameters
```

**Step 3**: Tune SLA thresholds based on observations
```python
# If emergency violations observed:
config.sla_J1_max = 0.05  # Stricter (was 0.10)
config.sla_eta1 = 0.03    # Faster adaptation

# If latency too high:
config.sla_J2_max_s = 3.0  # Stricter (was 5.0)

# If fairness issues:
config.sla_J3_max = 1.5    # Tighter ratio (was 2.0)
```

**Step 4**: Monitor adaptation
- Check α, β, γ weights over time
- Verify J1, J2, J3 metrics converge to targets
- Adjust η step sizes if oscillation observed

---

## Performance Summary

### Overall Rankings

**By Deadline Compliance (Load=30)**:
1. **SLA-DWP-Fog**: 0.00% violations ⭐⭐⭐⭐⭐
2. FIFO: 84.82% violations ⭐⭐
3. STATIC_PRIORITY: 92.96% violations ⭐
4. EMERGENCY_FIRST: 92.96% violations ⭐

**By Admission Rate (Load=30)**:
1. EMERGENCY_FIRST: 52.12% ⭐⭐⭐
2. STATIC_PRIORITY: 52.12% ⭐⭐⭐
3. FIFO: 51.15% ⭐⭐⭐
4. SLA-DWP-Fog: 42.99% ⭐⭐

**By Simplicity**:
1. FIFO: O(1), 1 parameter ⭐⭐⭐⭐⭐
2. EMERGENCY_FIRST: O(1), 1 parameter ⭐⭐⭐⭐⭐
3. STATIC_PRIORITY: O(1), 1 parameter ⭐⭐⭐⭐⭐
4. SLA-DWP-Fog: O(n), 8 parameters ⭐⭐

**Overall Best**: **SLA-DWP-Fog** for QoS-critical applications, **FIFO** for simplicity.

---

## Conclusion

**Key Takeaway**: There is no universally "best" scheduler—choice depends on application requirements.

**Decision Matrix**:

| Requirement | Recommended Scheduler |
|-------------|----------------------|
| Zero deadline violations | **SLA-DWP-Fog** |
| Maximum throughput | FIFO or STATIC_PRIORITY |
| Simplicity | FIFO |
| Emergency protection | SLA-DWP-Fog (not EMERGENCY_FIRST!) |
| Adaptive behavior | **SLA-DWP-Fog** |
| Low computational overhead | FIFO, EMERGENCY_FIRST, STATIC_PRIORITY |

**Research Contribution**: SLA-DWP-Fog demonstrates that proactive admission control with adaptive priorities can achieve 100× reduction in deadline violations (0% vs 85-93%) at the cost of 15-20% lower admission rate.

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Status**: Production
