# Quick Start Guide

## Overview

This guide helps you quickly set up, run, and analyze the SLA-DWP-Fog fog computing simulation framework.

---

## Installation

### Prerequisites

**Required**:
- Python 3.11 or higher
- pip package manager

**Operating Systems**:
- ✅ Windows 10/11
- ✅ Linux (Ubuntu 20.04+)
- ✅ macOS (10.15+)

### Install Dependencies

```powershell
# Navigate to project directory
cd c:\Users\kashy\OneDrive\Desktop\Project-Rework

# Install required packages
pip install numpy matplotlib python-pptx
```

**Package Versions** (tested):
- numpy: 1.24+
- matplotlib: 3.7+
- python-pptx: 0.6.21+

---

## Quick Start: 5-Minute Tutorial

### Step 1: Run Default Simulation

```powershell
python main.py
```

**Expected Output**:
```
Simulation completed.
Total generated: 18000
Total admitted: 14652
Total completed: 5293
Admission rate: 0.8140
Deadline miss rate: 0.0000
Emergency SLA met rate: 1.0000
```

**What This Does**:
- Runs 1-hour simulation (3600 seconds)
- Uses SLA-DWP-Fog scheduler (default)
- Average load: 5 requests/step
- 2×2 fog grid (4 nodes)

### Step 2: Try Different Scheduler

Edit `main.py`:
```python
config = SimulationConfig(
    scheduler="FIFO"  # Change from "SLA-DWP-Fog"
)
```

Run again:
```powershell
python main.py
```

**Compare Results**:
- FIFO: Higher admission, higher violations
- SLA-DWP-Fog: Lower admission, zero violations

### Step 3: Generate Comparison Plots

```powershell
python generate_comparison_plots.py
```

**Output**: 
- `plots/COMPARISON/fig1_deadline_miss.png`
- `plots/COMPARISON/fig5_admission_rate.png`
- Plus 3 more figures
- `comparison_results.json` with all data

**View Plots**: Open PNG files or check JSON for numerical results.

### Step 4: Create Presentation

```powershell
python generate_detailed_presentation.py
```

**Output**:
- `Detailed_SLA_DWP_Fog_Presentation.pptx` (45 slides, 2.6 MB)

**Content**:
- All 4 schedulers explained
- System architecture diagrams
- Performance tables with results
- All generated plots embedded

---

## Configuration Guide

### Basic Configuration

Edit `config.py` or override in your script:

```python
from config import SimulationConfig

config = SimulationConfig(
    # Simulation time
    sim_time=3600.0,          # Total time (seconds)
    time_step=1.0,            # Time step size
    
    # Topology
    num_fog_nodes_x=2,        # Grid: 2×2 = 4 nodes
    num_fog_nodes_y=2,
    
    # Resources
    fog_cpu_capacity=20.0,    # CPU units/second
    fog_link_capacity=200.0,  # MB/second
    fog_max_queue_length=300, # Max queue size
    
    # Workload
    avg_requests_per_step=5.0,  # Average arrivals
    
    # Scheduler
    scheduler="SLA-DWP-Fog"   # Or: FIFO, EMERGENCY_FIRST, STATIC_PRIORITY
)
```

### SLA-DWP-Fog Tuning

```python
config = SimulationConfig(
    scheduler="SLA-DWP-Fog",
    
    # SLA parameters
    sla_window_TW=10.0,       # Time window (seconds)
    sla_J1_max=0.10,          # Emergency miss threshold (10%)
    sla_J2_max_s=5.0,         # Latency threshold (5s)
    sla_J3_max=2.0,           # Fairness ratio threshold
    
    # Adaptation rates
    sla_eta1=0.02,            # Emergency step size
    sla_eta2=0.02,            # Latency step size
    sla_eta3=0.02,            # Fairness step size
    
    sla_eps=1e-6              # Numerical stability
)
```

**Tuning Tips**:
- **Lower J1_max** (e.g., 0.05): Stricter emergency SLA
- **Higher η** (e.g., 0.05): Faster adaptation (but risk oscillation)
- **Shorter TW** (e.g., 5s): More responsive (but less stable)

---

## Running Experiments

### Single Load Level

```python
from config import SimulationConfig
from simulation import Simulation

config = SimulationConfig(
    scheduler="SLA-DWP-Fog",
    avg_requests_per_step=30.0  # Load = 30
)

sim = Simulation(config)
results = sim.run()

print(f"Admission: {results['admission_rate']:.4f}")
print(f"Violations: {results['deadline_miss_rate']:.4f}")
```

### Multiple Load Levels

```python
loads = [2, 10, 30, 60, 100]
results_by_load = {}

for load in loads:
    config = SimulationConfig(
        scheduler="SLA-DWP-Fog",
        avg_requests_per_step=load
    )
    sim = Simulation(config)
    results_by_load[load] = sim.run()

# Analyze trends
for load, res in results_by_load.items():
    print(f"Load {load}: Admission={res['admission_rate']:.3f}, "
          f"Violations={res['deadline_miss_rate']:.3f}")
```

### Compare All Schedulers

```python
schedulers = ["FIFO", "EMERGENCY_FIRST", "STATIC_PRIORITY", "SLA-DWP-Fog"]
results_by_scheduler = {}

for sched in schedulers:
    config = SimulationConfig(
        scheduler=sched,
        avg_requests_per_step=30.0
    )
    sim = Simulation(config)
    results_by_scheduler[sched] = sim.run()

# Compare deadline performance
for sched, res in results_by_scheduler.items():
    print(f"{sched:20} Miss Rate: {res['deadline_miss_rate']:.4f}")
```

---

## Understanding Output

### Metrics Explained

**total_generated**: Number of requests created by workload generator
- Increases with `avg_requests_per_step`

**total_admitted**: Requests accepted into fog node queues
- = total_generated - total_rejected - total_dropped

**total_rejected**: Requests rejected by admission control (SLA-DWP-Fog only)
- Predicted to miss deadline → rejected before queueing

**total_dropped**: Requests dropped due to full queue
- Queue at max_queue_length capacity

**total_completed**: Requests successfully processed
- < total_admitted (some still in queue at sim end)

**admission_rate**: Fraction of requests accepted
- = total_admitted / total_generated
- SLA-DWP-Fog: ~80% at light load (proactive rejection)
- Others: ~100% at light load (accept until queue full)

**deadline_miss_rate**: Fraction of completed requests violating deadline
- = deadline_violated / total_completed
- SLA-DWP-Fog: **0.0000** (perfect compliance)
- FIFO: 0.8482 at load=30 (84.82% violations)

**emergency_sla_met_rate**: Emergency tasks meeting deadlines
- = priority3_deadline_met / (priority3_deadline_met + priority3_deadline_violated)
- Critical for safety (V2X applications)

**mean_latency**: Average end-to-end delay
- = mean(completion_time - arrival_time)
- Lower is better

**p95_latency**: 95th percentile latency (tail performance)
- Worst-case metric for real-time systems

---

## Troubleshooting

### Problem: "No module named 'numpy'"

**Solution**:
```powershell
pip install numpy matplotlib python-pptx
```

### Problem: Low Admission Rate with FIFO

**Check**:
```python
print(f"Queue length: {config.fog_max_queue_length}")
print(f"Load: {config.avg_requests_per_step}")
```

**If load >> capacity**:
- Reduce `avg_requests_per_step`, or
- Increase `fog_cpu_capacity`, or
- Increase `fog_max_queue_length`

### Problem: SLA-DWP-Fog Rejecting Too Many

**Tune admission**:
```python
# Option 1: Increase resources
config.fog_cpu_capacity = 40.0  # Double capacity

# Option 2: Looser SLA
config.sla_J2_max_s = 10.0  # Allow higher latency

# Option 3: Add more nodes
config.num_fog_nodes_x = 4  # 4×4 = 16 nodes
```

### Problem: Plots Not Generating

**Check paths**:
```powershell
# Ensure plots directory exists
mkdir plots\COMPARISON -Force

# Run with verbose
python generate_comparison_plots.py
```

**Check matplotlib backend**:
```python
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
```

---

## Advanced Usage

### Custom Request Types

Edit `models.py` and `request_generator.py`:

```python
# models.py
class RequestType(Enum):
    MY_NEW_TYPE = "my_new_type"

# request_generator.py
def _create_request(self, req_type: RequestType, current_time: float):
    if req_type == RequestType.MY_NEW_TYPE:
        return Request(
            request_id=self._next_id(),
            request_type=req_type,
            data_size=random.uniform(1.0, 2.0),
            processing_demand=random.uniform(2.0, 3.0),
            relative_deadline_s=random.uniform(2.0, 4.0),
            priority_class=2,  # Safety-Critical
            # ...
        )
```

### Custom Metrics

Edit `metrics.py`:

```python
class MetricsCollector:
    def __init__(self):
        # ... existing code ...
        self.my_custom_metric = 0
    
    def record_custom_event(self, value):
        self.my_custom_metric += value
    
    def final_report(self):
        report = {
            # ... existing metrics ...
            "my_custom_metric": self.my_custom_metric
        }
        return report
```

### Export to CSV

```python
import csv
from simulation import Simulation

# Run simulation
results = Simulation(config).run()

# Export to CSV
with open('results.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=results.keys())
    writer.writeheader()
    writer.writerow(results)
```

---

## Performance Tips

### Speed Up Simulations

**1. Reduce simulation time**:
```python
config.sim_time = 1800.0  # 30 minutes instead of 60
```

**2. Increase time step** (less accurate):
```python
config.time_step = 5.0  # 5-second steps instead of 1
```

**3. Disable detailed tracking**:
```python
# In metrics.py, comment out per-step tracking
# self.per_step_generated.append(len(requests))
```

### Memory Optimization

**For long simulations**:
```python
# In topology.py, limit history
if len(self._completed_history) > 1000:
    self._completed_history = self._completed_history[-1000:]
```

---

## Example Workflows

### Workflow 1: Research Paper Results

```powershell
# Step 1: Generate all comparison plots
python generate_comparison_plots.py

# Step 2: Generate extended analysis
python generate_extended_plots.py

# Step 3: Create presentation
python generate_detailed_presentation.py

# Step 4: Review outputs
# - plots/COMPARISON/*.png (5 main figures)
# - plots/extended/*.png (6 extended figures)
# - Detailed_SLA_DWP_Fog_Presentation.pptx (45 slides)
```

### Workflow 2: Parameter Tuning

```python
# test_parameters.py
from config import SimulationConfig
from simulation import Simulation

# Test different TW values
for tw in [5.0, 10.0, 20.0]:
    config = SimulationConfig(
        scheduler="SLA-DWP-Fog",
        sla_window_TW=tw,
        avg_requests_per_step=30.0
    )
    results = Simulation(config).run()
    print(f"TW={tw}s: Violations={results['deadline_miss_rate']:.4f}")
```

### Workflow 3: Validate Against Baseline

```python
# baseline.py
schedulers = ["FIFO", "SLA-DWP-Fog"]
load = 30.0

for sched in schedulers:
    config = SimulationConfig(scheduler=sched, avg_requests_per_step=load)
    results = Simulation(config).run()
    
    print(f"\n{sched}:")
    print(f"  Admission: {results['admission_rate']:.2%}")
    print(f"  Violations: {results['deadline_miss_rate']:.2%}")
    print(f"  Emergency SLA: {results.get('emergency_sla_met_rate', 0):.2%}")
```

**Expected Output**:
```
FIFO:
  Admission: 51.15%
  Violations: 84.82%
  Emergency SLA: 16.79%

SLA-DWP-Fog:
  Admission: 42.99%
  Violations: 0.00%
  Emergency SLA: 100.00%
```

---

## Next Steps

### Learn More

- **Algorithm Details**: Read `docs/SLA_DWP_Fog_Algorithm.md`
- **Architecture**: Read `docs/System_Architecture.md`
- **Comparisons**: Read `docs/Scheduler_Comparison.md`
- **Results**: Read `docs/Experimental_Results.md`

### Extend the Framework

1. **Add new schedulers**: Implement in `topology.py`
2. **Custom topologies**: Modify `build_grid_topology()`
3. **Real workloads**: Replace Poisson generator with trace replay
4. **Mobility**: Add dynamic user positions

### Reproduce Paper Results

```powershell
# Run the exact configuration from paper
python generate_comparison_plots.py

# Check figures match published plots
# - plots/COMPARISON/fig1_deadline_miss.png
# - plots/COMPARISON/fig5_admission_rate.png
```

---

## FAQs

**Q: Why does SLA-DWP-Fog have lower admission at light loads?**  
A: Time-based admission control proactively rejects tasks predicted to miss deadlines, even at low load.

**Q: Which scheduler should I use?**  
A: 
- Safety-critical (V2X, medical): **SLA-DWP-Fog**
- Best-effort (streaming, downloads): **FIFO**
- Simple priority (email tiers): **STATIC_PRIORITY**

**Q: How do I change the load?**  
A: Set `avg_requests_per_step` in config (higher = more load)

**Q: Can I run on 100+ fog nodes?**  
A: Yes, set `num_fog_nodes_x = 10, num_fog_nodes_y = 10` (100 nodes), but runtime increases.

**Q: How long does a simulation take?**  
A: 2-5 seconds for 3600s simulation on modern desktop.

---

## Getting Help

**Check Documentation**:
- `PROJECT_SUMMARY.md`: Project overview
- `docs/`: Detailed technical documentation

**Common Issues**:
- Import errors → Install dependencies
- Low performance → Check resource config
- Unexpected results → Verify random seed

**Contact**: [Your contact info here]

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Status**: Production
