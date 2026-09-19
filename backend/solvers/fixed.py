"""Fixed-time baseline signal controller."""
import time
from typing import Dict, List
from .. import config
from .base import SolveResult

class FixedTimeSolver:
    """Fixed-time signal controller.

    Operates on a 40s fixed cycle: 20s NS / 20s EW (with 3s lost time on transition).
    No adaptation to queues, no priority for emergency vehicles.
    """
    def __init__(self, cycle_s: int = config.FIXED_CYCLE_S):
        self.cycle_s = cycle_s
        self.half_cycle = cycle_s // 2 # 20s each direction

    def solve(self, current_time_s: int, intersection_ids: List[str], **kwargs) -> SolveResult:
        start_time = time.perf_counter()
        cycle_pos = current_time_s % self.cycle_s

        # 0..19: NS Green (0), 20..39: EW Green (1)
        phase = config.PHASE_NS if cycle_pos < self.half_cycle else config.PHASE_EW
        assignment = {node_id: phase for node_id in intersection_ids}

        # Lookahead plan for H slots
        plan_horizon = {}
        for node_id in intersection_ids:
            h_plan = []
            for t in range(config.HORIZON_H):
                t_future = current_time_s + t * config.SLOT_S
                pos = t_future % self.cycle_s
                h_plan.append(config.PHASE_NS if pos < self.half_cycle else config.PHASE_EW)
            plan_horizon[node_id] = h_plan

        elapsed = time.perf_counter() - start_time
        return SolveResult(
            assignment=assignment,
            cost=0.0,
            wall_time_s=elapsed,
            method="fixed",
            plan_horizon=plan_horizon,
            extra={"cycle_pos": cycle_pos}
        )
