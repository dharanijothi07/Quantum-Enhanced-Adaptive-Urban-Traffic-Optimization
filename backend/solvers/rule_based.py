"""Actuated queue-based baseline controller with emergency preemption."""
import time
from typing import Dict, List, Optional
from .. import config
from ..network import TrafficNetwork
from ..emergency import AmbulanceState
from .base import SolveResult

class RuleBasedSolver:
    """Actuated queue-based controller with min-green enforcement and ambulance preemption."""
    def __init__(self, threshold: int = config.RULE_THRESHOLD, min_green_s: int = config.MIN_GREEN_S):
        self.threshold = threshold
        self.min_green_s = min_green_s

    def solve(self, network: TrafficNetwork, current_time_s: int,
              ambulance: Optional[AmbulanceState] = None, **kwargs) -> SolveResult:
        start_time = time.perf_counter()
        assignment: Dict[str, int] = {}
        plan_horizon: Dict[str, List[int]] = {}

        # 1. Check for emergency ambulance preemption (within 1 link upstream)
        preempted_nodes: Dict[str, int] = {}
        if ambulance and ambulance.active and not ambulance.finished:
            curr_idx = ambulance.current_node_idx
            path = ambulance.route_node_ids
            if curr_idx < len(path):
                # The intersection directly ahead
                target_node_id = path[curr_idx]
                if curr_idx == 0:
                    req_phase = config.PHASE_EW
                else:
                    prev_node = network.intersections[path[curr_idx - 1]]
                    curr_node = network.intersections[target_node_id]
                    req_phase = config.PHASE_NS if curr_node.row != prev_node.row else config.PHASE_EW
                preempted_nodes[target_node_id] = req_phase

        # 2. Compute decisions per intersection
        for node_id, inter in network.intersections.items():
            # If ambulance is approaching this node, force preempted phase
            if node_id in preempted_nodes:
                target_phase = preempted_nodes[node_id]
            else:
                # Calculate effective queues for NS vs EW
                q_n = network.links[inter.approaches["N"]].queue if "N" in inter.approaches else 0
                q_s = network.links[inter.approaches["S"]].queue if "S" in inter.approaches else 0
                q_e = network.links[inter.approaches["E"]].queue if "E" in inter.approaches else 0
                q_w = network.links[inter.approaches["W"]].queue if "W" in inter.approaches else 0

                eff_ns = (q_n + q_s) + config.PED_WEIGHT * inter.ped_ns
                eff_ew = (q_e + q_w) + config.PED_WEIGHT * inter.ped_ew

                curr_phase = inter.phase
                # Check min green elapsed
                if inter.time_in_phase >= self.min_green_s:
                    if curr_phase == config.PHASE_NS and (eff_ew - eff_ns) >= self.threshold:
                        target_phase = config.PHASE_EW
                    elif curr_phase == config.PHASE_EW and (eff_ns - eff_ew) >= self.threshold:
                        target_phase = config.PHASE_NS
                    else:
                        target_phase = curr_phase
                else:
                    target_phase = curr_phase

            assignment[node_id] = target_phase
            plan_horizon[node_id] = [target_phase] * config.HORIZON_H

        elapsed = time.perf_counter() - start_time
        return SolveResult(
            assignment=assignment,
            cost=0.0,
            wall_time_s=elapsed,
            method="rule_based",
            plan_horizon=plan_horizon,
            extra={"preempted": list(preempted_nodes.keys())}
        )
