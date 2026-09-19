"""Unit tests for QUBO builder and Ising conversion (Phase 3 Gate)."""
import numpy as np
import pytest
from backend import config
from backend.network import TrafficNetwork
from backend.qubo import QUBOBuilder, qubo_cost_vector, ising_to_sparse_pauli_op

def test_ising_qubo_equivalence_200_bitstrings():
    """Verifies that for 200 random bitstrings, QUBO cost equals Ising energy with tolerance < 1e-6."""
    network = TrafficNetwork()
    builder = QUBOBuilder(network)
    # Populate some random traffic state
    for link in network.links.values():
        link.queue = int(np.random.randint(0, 15))
        link.recent_outflow = int(np.random.randint(0, 10))

    qubo = builder.build_qubo(current_time_s=100)
    cost_vec = qubo_cost_vector(qubo)
    n = qubo.n_vars

    rng = np.random.default_rng(42)
    sample_indices = rng.integers(0, 1 << n, size=200)

    for idx in sample_indices:
        idx = int(idx)
        qubo_val = cost_vec[idx]

        # Calculate Ising energy manually:
        # z_k = +1 if bit k == 0 else -1
        z = np.array([(1.0 if ((idx >> k) & 1) == 0 else -1.0) for k in range(n)])
        ising_energy = qubo.offset_ising + float(np.dot(qubo.h, z))
        
        # Quadratic Ising: sum_{k < l} J_kl z_k z_l
        quad_ising = 0.0
        for k in range(n):
            for l in range(k + 1, n):
                if abs(qubo.J[k, l]) > 1e-9:
                    quad_ising += qubo.J[k, l] * z[k] * z[l]
        ising_energy += quad_ising

        diff = abs(qubo_val - ising_energy)
        assert diff < 1e-6, f"Mismatch at idx {idx}: QUBO={qubo_val}, Ising={ising_energy}, diff={diff}"

    print("PASS: 200 random bitstrings verified with exact Ising-QUBO equivalence!")

def test_cost_vector_vectorization_parity():
    """Verifies that vectorized qubo_cost_vector agrees with single-state scalar evaluation on 50 states."""
    network = TrafficNetwork()
    builder = QUBOBuilder(network)
    qubo = builder.build_qubo(current_time_s=50)
    cost_vec = qubo_cost_vector(qubo)

    rng = np.random.default_rng(99)
    sample_indices = rng.integers(0, 1 << qubo.n_vars, size=50)

    for idx in sample_indices:
        idx = int(idx)
        bits = np.array([(idx >> k) & 1 for k in range(qubo.n_vars)], dtype=float)
        scalar_cost = float(qubo.offset + bits @ qubo.linear + 0.5 * bits @ qubo.quadratic @ bits)
        vector_cost = float(cost_vec[idx])
        assert abs(scalar_cost - vector_cost) < 1e-8, f"Mismatch at idx {idx}: scalar={scalar_cost}, vector={vector_cost}"

    print("PASS: 50 states verified for vectorized cost parity.")
