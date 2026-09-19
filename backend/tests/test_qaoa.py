"""Unit tests for QAOA, Simulated Annealing, and Exact Solvers (Phase 3 Gate)."""
import numpy as np
import pytest
from backend import config
from backend.network import TrafficNetwork
from backend.qubo import QUBOBuilder, qubo_cost_vector
from backend.solvers.exact import ExactBruteForceSolver
from backend.solvers.annealing import SimulatedAnnealingSolver
from backend.solvers.qaoa import QAOASolver

def test_qiskit_numpy_probability_match():
    """Verifies that Qiskit Aer and pure NumPy QAOA produce matching statevector probabilities."""
    network = TrafficNetwork()
    builder = QUBOBuilder(network)
    qubo = builder.build_qubo(current_time_s=10)
    cost_vec = qubo_cost_vector(qubo)

    qaoa_qiskit = QAOASolver(p=1, backend="qiskit")
    qaoa_numpy = QAOASolver(p=1, backend="numpy")

    test_params = np.array([0.35, 0.25])
    sv_qiskit = qaoa_qiskit._compute_statevector_qiskit(qubo.n_vars, qubo, test_params)
    sv_numpy = qaoa_numpy._compute_statevector_numpy(qubo.n_vars, cost_vec, test_params)

    probs_qiskit = np.abs(sv_qiskit) ** 2
    probs_numpy = np.abs(sv_numpy) ** 2

    max_diff = np.max(np.abs(probs_qiskit - probs_numpy))
    assert max_diff < 1e-6, f"Mismatch between Qiskit and NumPy: {max_diff}"
    print(f"PASS: Qiskit vs NumPy statevector matching verified (diff = {max_diff:.2e})")

def test_qaoa_expectation_decreases_vs_uniform():
    """Verifies that QAOA optimization lowers the cost expectation compared to the uniform random superposition."""
    network = TrafficNetwork()
    builder = QUBOBuilder(network)
    rng = np.random.default_rng(42)
    # Populate non-trivial queues deterministically
    for link in network.links.values():
        link.queue = int(rng.integers(2, 12))

    qubo = builder.build_qubo(current_time_s=20)
    cost_vec = qubo_cost_vector(qubo)

    # Uniform random superposition expectation is the mean cost across all 2^N states
    uniform_expectation = float(np.mean(cost_vec))

    # Run QAOA solver with enough iterations
    qaoa = QAOASolver(p=2, maxiter=40, time_budget_s=2.0, backend="numpy")
    res = qaoa.solve(qubo, cost_vec=cost_vec)

    qaoa_expectation = res.extra["expectation_val"]
    print(f"Uniform Expectation: {uniform_expectation:.2f}, QAOA Optimized Expectation: {qaoa_expectation:.2f}")
    assert qaoa_expectation <= uniform_expectation + 1e-6, "QAOA expectation should be <= uniform random state."
    assert res.cost <= uniform_expectation

def test_simulated_annealing_near_optimal():
    """Verifies that Simulated Annealing finds solutions close to the exact brute-force optimum."""
    network = TrafficNetwork()
    builder = QUBOBuilder(network)
    qubo = builder.build_qubo(current_time_s=30)
    cost_vec = qubo_cost_vector(qubo)

    exact_solver = ExactBruteForceSolver()
    exact_res = exact_solver.solve(qubo, cost_vec=cost_vec)

    sa_solver = SimulatedAnnealingSolver(steps=4000, seed=42)
    sa_res = sa_solver.solve(qubo, cost_vec=cost_vec)

    gap = (sa_res.cost - exact_res.cost) / max(abs(exact_res.cost), 1e-9)
    print(f"Exact Cost: {exact_res.cost:.2f}, SA Cost: {sa_res.cost:.2f}, Gap: {gap:.4f}")
    assert gap < 0.15, f"SA gap too large: {gap}"
