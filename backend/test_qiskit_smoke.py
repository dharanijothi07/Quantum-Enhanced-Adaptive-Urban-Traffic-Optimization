"""Qiskit Aer Smoke Test with Direct QAOA Quantum Circuit."""
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

def build_qaoa_circuit(n_qubits: int, linear_terms: dict, quadratic_terms: dict, gamma: float, beta: float) -> QuantumCircuit:
    """Constructs QAOA circuit (p=1) with cost unitary exp(-i*gamma*H_C) and mixer exp(-i*beta*H_M)."""
    qc = QuantumCircuit(n_qubits)
    # Hadamard initialization |+>^{\otimes n}
    qc.h(range(n_qubits))

    # Cost Hamiltonian evolution exp(-i * gamma * (sum h_k Z_k + sum J_kl Z_k Z_l))
    # RZ(theta) = exp(-i * theta/2 * Z), so theta = 2 * gamma * h_k
    for k, h_k in linear_terms.items():
        if abs(h_k) > 1e-9:
            qc.rz(2.0 * gamma * h_k, k)

    # RZZ(theta) = exp(-i * theta/2 * Z_k Z_l), so theta = 2 * gamma * J_kl
    for (k, l), J_kl in quadratic_terms.items():
        if abs(J_kl) > 1e-9:
            qc.rzz(2.0 * gamma * J_kl, k, l)

    # Mixer Hamiltonian evolution exp(-i * beta * sum X_k)
    # RX(theta) = exp(-i * theta/2 * X), so theta = 2 * beta
    for k in range(n_qubits):
        qc.rx(2.0 * beta, k)

    return qc

def run_smoke_test():
    print("--- Phase 1: Qiskit Aer Smoke Test with Canonical QAOA Circuit ---")
    n_qubits = 4
    # Ising Hamiltonian: H = 0.5 Z0 + 0.3 Z1 - 0.7 Z2 + 0.2 Z3 + 0.4 Z0 Z1 + 0.6 Z2 Z3
    linear = {0: 0.5, 1: 0.3, 2: -0.7, 3: 0.2}
    quadratic = {(0, 1): 0.4, (2, 3): 0.6}

    gamma = 0.45
    beta = 0.35

    qc = build_qaoa_circuit(n_qubits, linear, quadratic, gamma, beta)
    sim = AerSimulator(method="statevector")
    qc.save_statevector()
    
    t_qc = transpile(qc, sim)
    result = sim.run(t_qc).result()
    qiskit_sv = result.get_statevector(t_qc)
    qiskit_probs = np.abs(qiskit_sv.data) ** 2

    # NumPy reference computation
    dim = 2 ** n_qubits
    psi = np.ones(dim, dtype=complex) / np.sqrt(dim)

    cost_diag = np.zeros(dim)
    for idx in range(dim):
        z = [(1.0 if ((idx >> k) & 1) == 0 else -1.0) for k in range(n_qubits)]
        val = sum(linear[k] * z[k] for k in linear) + sum(quadratic[(k, l)] * z[k] * z[l] for (k, l) in quadratic)
        cost_diag[idx] = val

    # 1. Cost evolution
    psi = np.exp(-1j * gamma * cost_diag) * psi

    # 2. Mixer evolution (RX on each qubit)
    rx = np.array([[np.cos(beta), -1j * np.sin(beta)],
                   [-1j * np.sin(beta), np.cos(beta)]], dtype=complex)
    
    for k in range(n_qubits):
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

    numpy_probs = np.abs(psi) ** 2
    max_diff = np.max(np.abs(qiskit_probs - numpy_probs))
    print(f"Qiskit top 3 probabilities: {[round(float(x), 6) for x in sorted(qiskit_probs, reverse=True)[:3]]}")
    print(f"NumPy top 3 probabilities:  {[round(float(x), 6) for x in sorted(numpy_probs, reverse=True)[:3]]}")
    print(f"Max absolute difference between Qiskit and NumPy: {max_diff:.2e}")
    assert max_diff < 1e-12, f"Mismatch too large: {max_diff}"
    print("PASS: Qiskit Aer Statevector matches exact NumPy calculation with tolerance < 1e-12!")

if __name__ == "__main__":
    run_smoke_test()
