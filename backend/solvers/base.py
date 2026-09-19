"""Solver protocol and result data structures."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

@dataclass
class SolveResult:
    """Standardized output from any signal solver."""
    assignment: Dict[str, int] # {intersection_id: phase (0=NS, 1=EW)}
    cost: float
    wall_time_s: float
    method: str
    plan_horizon: Optional[Dict[str, List[int]]] = None # {intersection_id: [phase_0, phase_1, ...]}
    extra: Dict[str, Any] = field(default_factory=dict)

class TrafficSolver(Protocol):
    """Protocol implemented by all signal control solvers."""
    def solve(self, **kwargs) -> SolveResult:
        ...
