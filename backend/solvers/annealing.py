"""Simulated Annealing solver over the exact QUBO objective."""
import time
from typing import Dict, List, Optional
import numpy as np
from .. import config
from ..qubo import QUBORepresentation, qubo_cost_vector
from .base import SolveResult

class SimulatedAnnealingSolver:
    """Simulated Annealing on QUBO / Ising objective with geometric cooling."""
    def __init__(self, steps: int = config.SA_STEPS, t_initial: float = 100.0, t_final: float = 0.01, seed: int = 42):
        self.steps = steps
        self.t_initial = t_initial
        self.t_final = t_final
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def solve(self, qubo: QUBORepresentation, cost_vec: Optional[np.ndarray] = None, **kwargs) -> SolveResult:
        start_time = time.perf_counter()
        n = qubo.n_vars

        # Evaluate fast cost using cost_vec if available, otherwise vector multiplication
        if cost_vec is not None:
            def eval_cost(idx: int) -> float:
                return float(cost_vec[idx])
        else:
            def eval_cost(idx: int) -> float:
                bits = np.array([(idx >> k) & 1 for k in range(n)], dtype=float)
                return float(qubo.offset + bits @ qubo.linear + 0.5 * bits @ qubo.quadratic @ bits)

        # Initial random state
        curr_idx = self.rng.integers(0, 1 << n)
        curr_cost = eval_cost(curr_idx)
        best_idx = curr_idx
        best_cost = curr_cost

        decay = (self.t_final / self.t_initial) ** (1.0 / max(1, self.steps))
        t = self.t_initial

        for _ in range(self.steps):
            # Propose single-bit flip
            bit_to_flip = self.rng.integers(0, n)
            cand_idx = curr_idx ^ (1 << bit_to_flip)
            cand_cost = eval_cost(cand_idx)
            delta = cand_cost - curr_cost

            if delta < 0 or self.rng.random() < np.exp(-delta / max(1e-6, t)):
                curr_idx = cand_idx
                curr_cost = cand_cost
                if curr_cost < best_cost:
                    best_cost = curr_cost
                    best_idx = curr_idx

            t *= decay

        # Decode best solution
        assignment: Dict[str, int] = {}
        plan_horizon: Dict[str, List[int]] = {}

        for k in range(n):
            node_id, slot_t = qubo.inv_var_map[k]
            bit = (best_idx >> k) & 1
            if node_id not in plan_horizon:
                plan_horizon[node_id] = [0] * config.HORIZON_H
            plan_horizon[node_id][slot_t] = bit
            if slot_t == 0:
                assignment[node_id] = bit

        elapsed = time.perf_counter() - start_time
        return SolveResult(
            assignment=assignment,
            cost=best_cost,
            wall_time_s=elapsed,
            method="annealing",
            plan_horizon=plan_horizon,
            extra={"best_idx": best_idx, "steps": self.steps}
        )
