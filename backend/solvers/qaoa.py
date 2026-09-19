"""QAOA Traffic Signal Optimizer (Qiskit Aer Statevector + NumPy Fallback).

Exact verified Qiskit API pattern:
- Canonical QuantumCircuit(n) with H, RZ(2*gamma*h_k), RZZ(2*gamma*J_kl), and RX(2*beta)
- AerSimulator(method="statevector") + save_statevector()
- Exact diagonal expectation: probs @ cost_vector
- Scipy minimize COBYLA with wall-clock budget enforcement
- Top-K classical post-selection on final statevector distribution
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from scipy.optimize import minimize
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

from .. import config
from ..qubo import QUBORepresentation, qubo_cost_vector, ising_to_sparse_pauli_op
from .base import SolveResult
from .exact import ExactBruteForceSolver

class QAOASolver:
    """Quantum Approximate Optimization Algorithm (QAOA) for traffic signal control."""
    def __init__(self, p: int = config.QAOA_REPS, maxiter: int = config.QAOA_MAXITER,
                 time_budget_s: float = config.QAOA_TIME_BUDGET_S, backend: str = "qiskit"):
        self.p = p
        self.maxiter = maxiter
        self.time_budget_s = time_budget_s
        self.backend = backend # "qiskit" or "numpy"
        self.last_params: Optional[np.ndarray] = None
        self.exact_solver = ExactBruteForceSolver()
        self.qiskit_sim = AerSimulator(method="statevector") if backend == "qiskit" else None

    def _init_params(self) -> np.ndarray:
        """Initializes QAOA parameters using linear ramp."""
        # gamma from 0.1 up, beta from 0.4 down
        gammas = np.linspace(0.1, 0.4, self.p)
        betas = np.linspace(0.4, 0.1, self.p)
        return np.concatenate([gammas, betas])

    def _compute_statevector_numpy(self, n: int, cost_diag: np.ndarray, params: np.ndarray) -> np.ndarray:
        """Computes QAOA statevector using pure NumPy."""
        dim = 1 << n
        psi = np.ones(dim, dtype=complex) / np.sqrt(dim)
        gammas = params[:self.p]
        betas = params[self.p:]

        rx_gates = []
        for beta in betas:
            rx = np.array([[np.cos(beta), -1j * np.sin(beta)],
                           [-1j * np.sin(beta), np.cos(beta)]], dtype=complex)
            rx_gates.append(rx)

        for layer in range(self.p):
            gamma = gammas[layer]
            rx = rx_gates[layer]

            # 1. Cost Hamiltonian Phase: exp(-i * gamma * H_C)
            psi = np.exp(-1j * gamma * cost_diag) * psi

            # 2. Mixer Hamiltonian: exp(-i * beta * sum X_k)
            for k in range(n):
                new_psi = np.zeros_like(psi)
                step = 1 << k
                for idx in range(dim):
                    if (idx & step) == 0:
                        idx0 = idx
                        idx1 = idx | step
                        v0 = psi[idx0]
                        v1 = psi[idx1]
                        new_psi[idx0] = rx[0, 0] * v0 + rx[0, 1] * v1
                        new_psi[idx1] = rx[1, 0] * v0 + rx[1, 1] * v1
                psi = new_psi

        return psi

    def _compute_statevector_qiskit(self, n: int, qubo: QUBORepresentation, params: np.ndarray) -> np.ndarray:
        """Computes QAOA statevector using Qiskit AerSimulator."""
        gammas = params[:self.p]
        betas = params[self.p:]

        qc = QuantumCircuit(n)
        qc.h(range(n))

        for layer in range(self.p):
            gamma = gammas[layer]
            beta = betas[layer]

            # Linear RZ terms
            for k in range(n):
                if abs(qubo.h[k]) > 1e-9:
                    qc.rz(2.0 * gamma * qubo.h[k], k)

            # Quadratic RZZ terms
            for k in range(n):
                for l in range(k + 1, n):
                    if abs(qubo.J[k, l]) > 1e-9:
                        qc.rzz(2.0 * gamma * qubo.J[k, l], k, l)

            # Mixer RX terms
            for k in range(n):
                qc.rx(2.0 * beta, k)

        qc.save_statevector()
        t_qc = transpile(qc, self.qiskit_sim)
        result = self.qiskit_sim.run(t_qc).result()
        sv = result.get_statevector(t_qc)
        return np.array(sv.data)

    def solve(self, qubo: QUBORepresentation, cost_vec: Optional[np.ndarray] = None, **kwargs) -> SolveResult:
        start_time = time.perf_counter()
        n = qubo.n_vars

        if cost_vec is None:
            cost_vec = qubo_cost_vector(qubo)

        # Initial point with warm-start
        x0 = self.last_params if self.last_params is not None else self._init_params()

        # Exact optimum reference for gap calculation
        exact_res = self.exact_solver.solve(qubo, cost_vec=cost_vec)
        exact_cost = exact_res.cost

        # Objective function for classical parameter optimizer (COBYLA)
        eval_count = 0
        best_exp = float("inf")
        best_params = x0.copy()
        time_limit = start_time + self.time_budget_s

        def eval_point(params: np.ndarray) -> Tuple[float, np.ndarray]:
            if self.backend == "qiskit" and self.qiskit_sim is not None:
                try:
                    sv_data = self._compute_statevector_qiskit(n, qubo, params)
                except Exception:
                    sv_data = self._compute_statevector_numpy(n, cost_vec, params)
            else:
                sv_data = self._compute_statevector_numpy(n, cost_vec, params)
            probs = np.abs(sv_data) ** 2
            return float(probs @ cost_vec), sv_data

        # Evaluate initial point
        try:
            init_exp, _ = eval_point(x0)
            best_exp = init_exp
        except Exception:
            best_exp = float("inf")

        def objective(params: np.ndarray) -> float:
            nonlocal eval_count, best_exp, best_params
            eval_count += 1

            # Check time budget
            if time.perf_counter() > time_limit:
                return best_exp

            exp_val, _ = eval_point(params)

            if exp_val < best_exp:
                best_exp = exp_val
                best_params = params.copy()

            return exp_val

        # Run COBYLA optimizer
        opt_res = minimize(
            objective,
            x0=x0,
            method="COBYLA",
            options={"maxiter": self.maxiter}
        )

        opt_params = best_params
        self.last_params = opt_params.copy()

        # Compute final probability vector at optimized parameters
        if self.backend == "qiskit" and self.qiskit_sim is not None:
            final_sv = self._compute_statevector_qiskit(n, qubo, opt_params)
        else:
            final_sv = self._compute_statevector_numpy(n, cost_vec, opt_params)

        final_probs = np.abs(final_sv) ** 2
        final_expectation = float(final_probs @ cost_vec)

        # Hybrid classical post-processing: top-K bitstrings
        top_k_indices = np.argsort(final_probs)[::-1][:config.QAOA_TOP_K]
        best_bitstring_idx = int(top_k_indices[np.argmin(cost_vec[top_k_indices])])
        best_cost = float(cost_vec[best_bitstring_idx])

        # Optimality gap
        denom = max(abs(exact_cost), 1e-9)
        gap = max(0.0, (best_cost - exact_cost) / denom)
        approx_ratio = exact_cost / max(final_expectation, 1e-9) if exact_cost != 0 else 1.0

        # Decode best assignment
        assignment: Dict[str, int] = {}
        plan_horizon: Dict[str, List[int]] = {}

        for k in range(n):
            node_id, slot_t = qubo.inv_var_map[k]
            bit = (best_bitstring_idx >> k) & 1
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
            method="qaoa",
            plan_horizon=plan_horizon,
            extra={
                "qubits": n,
                "p": self.p,
                "iters": eval_count,
                "expectation_val": round(final_expectation, 2),
                "best_cost": round(best_cost, 2),
                "exact_cost": round(exact_cost, 2),
                "gap": round(gap, 4),
                "approx_ratio": round(approx_ratio, 3),
                "backend_used": self.backend,
                "best_idx": best_bitstring_idx
            }
        )
