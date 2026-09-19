"""Brute-force exact optimizer for ground-truth reference (n <= 20)."""
import time
from typing import Dict, List, Optional
import numpy as np
from .. import config
from ..qubo import QUBORepresentation, qubo_cost_vector
from .base import SolveResult

class ExactBruteForceSolver:
    """Computes the exact global optimum bitstring via vectorized enumeration."""
    def solve(self, qubo: QUBORepresentation, cost_vec: Optional[np.ndarray] = None, **kwargs) -> SolveResult:
        start_time = time.perf_counter()
        n = qubo.n_vars
        if n > 20:
            raise ValueError(f"Exact solver only supports n <= 20 qubits (received {n})")

        if cost_vec is None:
            cost_vec = qubo_cost_vector(qubo)

        best_idx = int(np.argmin(cost_vec))
        min_cost = float(cost_vec[best_idx])

        # Convert best_idx to bit assignment per intersection for slot 0 and full horizon
        assignment: Dict[str, int] = {}
        plan_horizon: Dict[str, List[int]] = {}

        for k in range(n):
            node_id, t = qubo.inv_var_map[k]
            bit = (best_idx >> k) & 1
            if node_id not in plan_horizon:
                plan_horizon[node_id] = [0] * config.HORIZON_H
            plan_horizon[node_id][t] = bit
            if t == 0:
                assignment[node_id] = bit

        elapsed = time.perf_counter() - start_time
        return SolveResult(
            assignment=assignment,
            cost=min_cost,
            wall_time_s=elapsed,
            method="exact",
            plan_horizon=plan_horizon,
            extra={"best_idx": best_idx, "n_vars": n}
        )
