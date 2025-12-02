# Contributing to SLA-DWP-Fog

Thank you for your interest in contributing to the SLA-DWP-Fog project! We welcome contributions from the community.

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- Familiarity with fog computing and scheduling algorithms

### Setup Development Environment

```bash
# Fork and clone the repository
git clone https://github.com/yourusername/sla-dwp-fog.git
cd sla-dwp-fog

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python main.py
```

---

## 🤝 How to Contribute

### 1. Reporting Bugs

If you find a bug, please open an issue with:

- **Title**: Clear, descriptive summary
- **Description**: Detailed explanation of the problem
- **Steps to Reproduce**: Minimal code to reproduce the issue
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: OS, Python version, dependency versions
- **Screenshots/Logs**: If applicable

**Example:**

```markdown
**Title**: SLA-DWP-Fog raises ValueError with negative load

**Description**: When `avg_requests_per_step` is set to a negative value, the simulation crashes with a ValueError.

**Steps to Reproduce**:
```python
config = SimulationConfig(avg_requests_per_step=-5.0)
sim = Simulation(config)
sim.run()  # ValueError: Poisson parameter must be non-negative
```

**Expected**: Should raise a clear validation error at config creation
**Actual**: Crashes during simulation with cryptic message
**Environment**: Windows 11, Python 3.11.9, numpy 1.24.3
```

### 2. Suggesting Enhancements

Feature requests are welcome! Please include:

- **Use Case**: Why is this feature needed?
- **Proposed Solution**: How should it work?
- **Alternatives**: Other approaches considered
- **Impact**: Who benefits and how?

### 3. Submitting Pull Requests

#### Step 1: Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

**Branch Naming Convention:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/improvements

#### Step 2: Make Your Changes

Follow the code style guidelines (see below).

#### Step 3: Test Your Changes

```bash
# Run existing simulations
python main.py

# Verify all schedulers work
for sched in ["FIFO", "EMERGENCY_FIRST", "STATIC_PRIORITY", "SLA-DWP-Fog"]:
    # Test with scheduler

# Generate plots to verify no breaking changes
python generate_comparison_plots.py
```

#### Step 4: Commit Your Changes

```bash
git add .
git commit -m "feat: Add custom scheduler support"
```

**Commit Message Format:**
```
<type>: <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Example:**
```
feat: Add EDF (Earliest Deadline First) scheduler

- Implement EDF scheduling logic in topology.py
- Add configuration parameter for EDF
- Update comparison plots to include EDF
- Add EDF section to Scheduler_Comparison.md

Closes #42
```

#### Step 5: Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub with:
- **Title**: Clear description of changes
- **Description**: What, why, and how
- **Related Issues**: Link to any related issues
- **Testing**: How you tested the changes
- **Screenshots**: If UI/visual changes

---

## 📝 Code Style Guidelines

### Python Style (PEP 8)

```python
# Good
def calculate_priority_score(request: Request, current_time: float) -> float:
    """
    Calculate normalized priority score for a request.
    
    Args:
        request: The incoming request
        current_time: Current simulation time
        
    Returns:
        Priority score in range [0, 1]
    """
    urgency = (request.absolute_deadline - current_time) / request.relative_deadline_s
    return min(max(urgency, 0.0), 1.0)

# Bad
def calc_pri(r,t):  # No type hints, unclear names
    u=(r.absolute_deadline-t)/r.relative_deadline_s  # No spaces
    return min(max(u,0.0),1.0)
```

### Type Hints

Always include type hints for function signatures:

```python
from typing import List, Dict, Optional, Tuple

def process_requests(
    requests: List[Request], 
    current_time: float
) -> Tuple[List[Request], Dict[str, int]]:
    ...
```

### Docstrings

Use Google-style docstrings for all public functions and classes:

```python
def enqueue_request(self, request: Request, time_step: float) -> Tuple[bool, Optional[str]]:
    """
    Attempt to enqueue a request with admission control.
    
    Args:
        request: Incoming request to enqueue
        time_step: Current time step duration
        
    Returns:
        Tuple of (admitted: bool, rejection_reason: Optional[str])
        - (True, None): Request admitted successfully
        - (False, "queue_full"): Queue at capacity
        - (False, "admission_rejected"): Failed admission control
        
    Raises:
        ValueError: If time_step is negative
    """
    ...
```

### Variable Naming

- **Classes**: PascalCase (`FogNode`, `SimulationConfig`)
- **Functions/Methods**: snake_case (`process_one_step`, `calculate_latency`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_QUEUE_LENGTH`, `DEFAULT_CAPACITY`)
- **Private Methods**: Leading underscore (`_update_weights`, `_select_request`)

### Code Organization

```python
# 1. Standard library imports
import random
from dataclasses import dataclass
from typing import List, Optional

# 2. Third-party imports
import numpy as np
import matplotlib.pyplot as plt

# 3. Local imports
from config import SimulationConfig
from models import Request, RequestType

# 4. Constants
DEFAULT_CAPACITY = 100.0
MAX_RETRIES = 3

# 5. Classes and functions
class FogNode:
    ...
```

---

## 🧪 Testing Guidelines

### Manual Testing

Before submitting, test:

1. **Basic Functionality**:
```bash
python main.py
```

2. **All Schedulers**:
```python
for scheduler in ["FIFO", "EMERGENCY_FIRST", "STATIC_PRIORITY", "SLA-DWP-Fog"]:
    config = SimulationConfig(scheduler=scheduler)
    results = Simulation(config).run()
    assert results['total_completed'] > 0
```

3. **Edge Cases**:
```python
# Zero load
config = SimulationConfig(avg_requests_per_step=0.0)

# Heavy load
config = SimulationConfig(avg_requests_per_step=200.0)

# Single node
config = SimulationConfig(num_fog_nodes_x=1, num_fog_nodes_y=1)
```

### Adding Tests (Future)

When we add `pytest`:

```python
# tests/test_scheduler.py
import pytest
from topology import FogNode
from models import Request, RequestType

def test_fifo_ordering():
    """FIFO scheduler should process requests in arrival order."""
    node = FogNode(node_id=0, position=(0, 0), cpu_capacity=10.0, scheduler="FIFO")
    
    # Create requests with different arrival times
    req1 = Request(..., arrival_time=1.0)
    req2 = Request(..., arrival_time=2.0)
    
    node.enqueue_request(req1, time_step=1.0)
    node.enqueue_request(req2, time_step=1.0)
    
    # Process - req1 should complete first
    completed = node.process_one_step(current_time=3.0, time_step=1.0)
    assert completed[0].request_id == req1.request_id
```

---

## 📚 Documentation Guidelines

### Update Documentation When:

- Adding new features
- Changing APIs
- Adding new configuration parameters
- Implementing new schedulers

### Documentation Files to Update:

1. **README.md**: High-level changes, new features
2. **docs/API_Reference.md**: New classes/functions
3. **docs/Quick_Start_Guide.md**: New usage patterns
4. **Docstrings**: All new code

### Example Documentation Addition:

```markdown
### Class: `CustomScheduler`

**Description**: Implements custom scheduling logic based on XYZ.

**Constructor**:
```python
CustomScheduler(
    param1: float,
    param2: str = "default"
)
```

**Methods**:

#### `schedule(requests: List[Request]) -> Request`

Select next request to process.

**Parameters**:
- `requests`: Available requests

**Returns**: Selected request or None

**Example**:
```python
scheduler = CustomScheduler(param1=1.5)
next_req = scheduler.schedule(available_requests)
```
```

---

## 🎯 Contribution Ideas

### Good First Issues

- Add input validation for `SimulationConfig`
- Improve error messages for common mistakes
- Add examples to documentation
- Create tutorial notebooks
- Add unit tests for existing functions

### Advanced Contributions

- Implement new scheduling algorithms (EDF, LLF, etc.)
- Add support for heterogeneous fog nodes
- Implement dynamic topology (node failures)
- Add real workload traces
- Create web-based visualization dashboard
- Optimize performance for large-scale simulations

---

## 🔍 Code Review Process

All submissions go through code review:

1. **Automated Checks**: Style, basic tests (when implemented)
2. **Maintainer Review**: Logic, design, documentation
3. **Discussion**: Suggestions, improvements
4. **Approval**: Once all feedback addressed
5. **Merge**: Into main branch

### Review Criteria

- ✅ Follows code style guidelines
- ✅ Includes appropriate documentation
- ✅ Passes all existing simulations
- ✅ Doesn't break existing functionality
- ✅ Addresses the stated problem/feature
- ✅ Has clear, descriptive commit messages

---

## 🏆 Recognition

Contributors will be:
- Listed in AUTHORS file
- Mentioned in release notes
- Credited in academic papers (if applicable)

---

## ❓ Questions?

- **General Questions**: Open a GitHub Discussion
- **Bug Reports**: Open an Issue
- **Security Issues**: Email maintainers directly
- **Feature Requests**: Open an Issue with "enhancement" label

---

## 📜 Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive Behavior:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable Behavior:**
- Trolling, insulting/derogatory comments, personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

### Enforcement

Violations may result in temporary or permanent ban from the project.

---

## 📞 Contact

- **Maintainers**: [List maintainer emails/GitHub handles]
- **Project Lead**: your.email@example.com
- **Issues**: https://github.com/yourusername/sla-dwp-fog/issues

---

**Thank you for contributing to SLA-DWP-Fog! 🎉**

Every contribution, no matter how small, helps improve fog computing research.
