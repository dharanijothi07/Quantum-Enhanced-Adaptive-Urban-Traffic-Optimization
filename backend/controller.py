"""Receding-horizon multi-intersection traffic signal controller with async solve and fallback."""
import asyncio
import concurrent.futures
import time
from typing import Dict, List, Optional, Tuple
import numpy as np

from . import config
from .network import TrafficNetwork
from .qubo import QUBOBuilder, qubo_cost_vector
from .solvers.base import SolveResult
from .solvers.annealing import SimulatedAnnealingSolver
from .solvers.qaoa import QAOASolver

def _solve_qaoa_worker(qubo, cost_vec, last_params, p, maxiter, time_budget, backend):
    """Worker function for async execution in process pool."""
    solver = QAOASolver(p=p, maxiter=maxiter, time_budget_s=time_budget, backend=backend)
    solver.last_params = last_params
    return solver.solve(qubo, cost_vec=cost_vec)

class RecedingHorizonController:
    """Controls signals every SLOT_S simulated seconds via QUBO and QAOA/SA."""
    def __init__(self, network: TrafficNetwork, solver_type: str = "qaoa", backend: str = "qiskit"):
        self.network = network
        self.solver_type = solver_type
        self.backend = backend
        self.qubo_builder = QUBOBuilder(network)
        self.sa_fallback_solver = SimulatedAnnealingSolver(steps=config.SA_STEPS)
        self.qaoa_solver = QAOASolver(backend=backend)
        
        self.last_result: Optional[SolveResult] = None
        self.last_applied_plan: Dict[str, int] = {node_id: config.PHASE_NS for node_id in network.intersections}
        self.late_solves: int = 0
        self.fallback_count: int = 0

    def solve_step(self, current_time_s: int, emergency_biases: Optional[Dict[Tuple[str, int], int]] = None) -> SolveResult:
        """Synchronously builds QUBO and solves for next slot decisions."""
        start_t = time.perf_counter()
        qubo = self.qubo_builder.build_qubo(current_time_s, emergency_biases=emergency_biases)
        cost_vec = qubo_cost_vector(qubo)

        if self.solver_type == "annealing":
            result = self.sa_fallback_solver.solve(qubo, cost_vec=cost_vec)
        elif self.solver_type == "qaoa":
            # Direct fast solve
            try:
                result = self.qaoa_solver.solve(qubo, cost_vec=cost_vec)
            except Exception as e:
                # SA Fallback on error/budget
                self.fallback_count += 1
                result = self.sa_fallback_solver.solve(qubo, cost_vec=cost_vec)
                result.extra["fallback_used"] = True
                result.extra["error"] = str(e)
        else:
            # Fallback SA
            result = self.sa_fallback_solver.solve(qubo, cost_vec=cost_vec)

        self.last_result = result
        self.last_applied_plan = result.assignment
        return result
