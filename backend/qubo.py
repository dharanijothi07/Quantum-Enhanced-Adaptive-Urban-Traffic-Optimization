"""QUBO and Ising Hamiltonian formulation for multi-intersection signal control."""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
from qiskit.quantum_info import SparsePauliOp
from . import config
from .network import TrafficNetwork, Link, Intersection
from .emergency import EmergencyManager

@dataclass
class QUBORepresentation:
    n_vars: int
    var_map: Dict[Tuple[str, int], int] # (node_id, slot_t) -> variable index k
    inv_var_map: Dict[int, Tuple[str, int]] # index k -> (node_id, slot_t)
    linear: np.ndarray # shape (n_vars,)
    quadratic: np.ndarray # shape (n_vars, n_vars), symmetric or upper triangular
    offset: float # constant term

    # Ising Hamiltonian parameters: H = offset_ising + sum h_k Z_k + sum J_kl Z_k Z_l
    h: np.ndarray
    J: np.ndarray
    offset_ising: float

class QUBOBuilder:
    """Builds QUBO objective matrix and converts to Ising Hamiltonian."""
    def __init__(self, network: TrafficNetwork, horizon_h: int = config.HORIZON_H, slot_s: int = config.SLOT_S):
        self.network = network
        self.horizon_h = horizon_h
        self.slot_s = slot_s

        # Map (node_id, t) to index k in 0..N-1
        self.node_ids = sorted(list(network.intersections.keys()))
        self.var_map: Dict[Tuple[str, int], int] = {}
        self.inv_var_map: Dict[int, Tuple[str, int]] = {}
        idx = 0
        for node_id in self.node_ids:
            for t in range(self.horizon_h):
                self.var_map[(node_id, t)] = idx
                self.inv_var_map[idx] = (node_id, t)
                idx += 1
        self.n_vars = idx

    def build_qubo(self, current_time_s: int, emergency_biases: Optional[Dict[Tuple[str, int], int]] = None) -> QUBORepresentation:
        """Constructs QUBO matrix summing all 6 documented terms."""
        linear = np.zeros(self.n_vars, dtype=float)
        quadratic = np.zeros((self.n_vars, self.n_vars), dtype=float)
        offset = 0.0

        # 1. Delay / Service Term (Linear)
        for node_id in self.node_ids:
            inter = self.network.intersections[node_id]
            # Current approach queues
            q_n = self.network.links[inter.approaches["N"]].queue if "N" in inter.approaches and not self.network.links[inter.approaches["N"]].discharge_blocked else 0
            q_s = self.network.links[inter.approaches["S"]].queue if "S" in inter.approaches and not self.network.links[inter.approaches["S"]].discharge_blocked else 0
            q_e = self.network.links[inter.approaches["E"]].queue if "E" in inter.approaches and not self.network.links[inter.approaches["E"]].discharge_blocked else 0
            q_w = self.network.links[inter.approaches["W"]].queue if "W" in inter.approaches and not self.network.links[inter.approaches["W"]].discharge_blocked else 0

            cap_n = self.network.links[inter.approaches["N"]].effective_capacity if "N" in inter.approaches else config.DEFAULT_LINK_CAPACITY
            cap_s = self.network.links[inter.approaches["S"]].effective_capacity if "S" in inter.approaches else config.DEFAULT_LINK_CAPACITY
            cap_e = self.network.links[inter.approaches["E"]].effective_capacity if "E" in inter.approaches else config.DEFAULT_LINK_CAPACITY
            cap_w = self.network.links[inter.approaches["W"]].effective_capacity if "W" in inter.approaches else config.DEFAULT_LINK_CAPACITY

            arr_n = self.network.links[inter.approaches["N"]].arrival_rate if "N" in inter.approaches else 0.0
            arr_s = self.network.links[inter.approaches["S"]].arrival_rate if "S" in inter.approaches else 0.0
            arr_e = self.network.links[inter.approaches["E"]].arrival_rate if "E" in inter.approaches else 0.0
            arr_w = self.network.links[inter.approaches["W"]].arrival_rate if "W" in inter.approaches else 0.0

            sat_slot = config.SATURATION_FLOW_RATE * self.slot_s

            for t in range(self.horizon_h):
                k = self.var_map[(node_id, t)]
                # Forecast queues for slot t
                q_n_t = min(cap_n, q_n + arr_n * t * self.slot_s)
                q_s_t = min(cap_s, q_s + arr_s * t * self.slot_s)
                q_e_t = min(cap_e, q_e + arr_e * t * self.slot_s)
                q_w_t = min(cap_w, q_w + arr_w * t * self.slot_s)

                # Add pedestrian weight
                q_ns_eff = (q_n_t + q_s_t) + config.PED_WEIGHT * inter.ped_ns
                q_ew_eff = (q_e_t + q_w_t) + config.PED_WEIGHT * inter.ped_ew

                # Cost when x=0 (NS green): EW waits, NS served
                a0 = config.W_WAIT * q_ew_eff * self.slot_s - config.W_THRU * min(q_ns_eff, sat_slot)
                # Cost when x=1 (EW green): NS waits, EW served
                a1 = config.W_WAIT * q_ns_eff * self.slot_s - config.W_THRU * min(q_ew_eff, sat_slot)

                offset += a0
                linear[k] += (a1 - a0)

        # 2. Switching Penalty (Quadratic & Linear)
        for node_id in self.node_ids:
            inter = self.network.intersections[node_id]
            curr_phase = inter.phase

            # Slot 0 against currently applied phase p_i: W_SWITCH * (x[i,0] - p_i)^2
            k0 = self.var_map[(node_id, 0)]
            if curr_phase == 0:
                # (x - 0)^2 = x
                linear[k0] += config.W_SWITCH
            else:
                # (x - 1)^2 = 1 - x
                offset += config.W_SWITCH
                linear[k0] -= config.W_SWITCH

            # Between future slots: W_SWITCH * (x_t - x_{t+1})^2 = W_SWITCH * (x_t + x_{t+1} - 2*x_t*x_{t+1})
            for t in range(self.horizon_h - 1):
                kt = self.var_map[(node_id, t)]
                kt1 = self.var_map[(node_id, t + 1)]
                linear[kt] += config.W_SWITCH
                linear[kt1] += config.W_SWITCH
                quadratic[kt, kt1] -= 2.0 * config.W_SWITCH

        # 3. Green-Wave Coordination (Quadratic)
        for link in self.network.links.values():
            if link.is_boundary_entry or link.is_boundary_exit:
                continue
            u, v = link.from_node, link.to_node
            if u not in self.network.intersections or v not in self.network.intersections:
                continue

            flow_uv = max(1.0, float(link.recent_outflow))
            for t in range(self.horizon_h - 1):
                ku = self.var_map[(u, t)]
                kv = self.var_map[(v, t + 1)]

                if link.orientation == "NS":
                    # Reward (1 - x_u) * (1 - x_v) = 1 - x_u - x_v + x_u * x_v
                    coeff = config.W_WAVE * flow_uv
                    offset -= coeff
                    linear[ku] += coeff
                    linear[kv] += coeff
                    quadratic[ku, kv] -= coeff
                else:
                    # Reward x_u * x_v
                    coeff = config.W_WAVE * flow_uv
                    quadratic[ku, kv] -= coeff

        # 4. Spillback Protection (Linear)
        for node_id in self.node_ids:
            inter = self.network.intersections[node_id]
            # Check storage ratio of outgoing links for NS vs EW
            for app_dir, link_id in inter.approaches.items():
                link = self.network.links.get(link_id)
                if not link:
                    continue
                ratio = link.storage_ratio
                if ratio >= 0.8:
                    # High queue on incoming approach -> penalty if we DO NOT serve it
                    # If NS approach is full, choosing EW (x=1) is penalized
                    for t in range(self.horizon_h):
                        k = self.var_map[(node_id, t)]
                        if app_dir in ["N", "S"]:
                            linear[k] += config.W_SPILL * ratio
                        else:
                            # EW approach full, choosing NS (x=0) is penalized
                            offset += config.W_SPILL * ratio
                            linear[k] -= config.W_SPILL * ratio

        # 5. Emergency Green Corridor (Linear, Large Bias M)
        if emergency_biases:
            for (node_id, t), req_phase in emergency_biases.items():
                if (node_id, t) in self.var_map:
                    k = self.var_map[(node_id, t)]
                    if req_phase == config.PHASE_NS:
                        # NS required (x=0 required) -> penalize x=1 with +M
                        linear[k] += config.W_EMERGENCY
                    else:
                        # EW required (x=1 required) -> penalize x=0 with +M
                        offset += config.W_EMERGENCY
                        linear[k] -= config.W_EMERGENCY

        # Symmetrize quadratic matrix
        quadratic_sym = quadratic + quadratic.T - np.diag(np.diag(quadratic))

        # Convert to Ising Hamiltonian: x_k = (1 - z_k)/2
        # x_k = 0.5 - 0.5 z_k
        # x_k x_l = 0.25 - 0.25 z_k - 0.25 z_l + 0.25 z_k z_l
        # Constant offset_ising:
        # offset_ising = offset + 0.5 * sum(linear) + sum_{k < l} 0.25 * quadratic_sym[k, l]
        # h_k = -0.5 * linear[k] - sum_{l != k} 0.25 * quadratic_sym[k, l]
        # J_kl = 0.25 * quadratic_sym[k, l] for k < l

        h = np.zeros(self.n_vars, dtype=float)
        J = np.zeros((self.n_vars, self.n_vars), dtype=float)
        offset_ising = offset + 0.5 * np.sum(linear)

        for k in range(self.n_vars):
            h[k] = -0.5 * linear[k]

        for k in range(self.n_vars):
            for l in range(k + 1, self.n_vars):
                q_kl = quadratic_sym[k, l]
                if abs(q_kl) > 1e-9:
                    J[k, l] = 0.25 * q_kl
                    h[k] -= 0.25 * q_kl
                    h[l] -= 0.25 * q_kl
                    offset_ising += 0.25 * q_kl

        return QUBORepresentation(
            n_vars=self.n_vars,
            var_map=self.var_map,
            inv_var_map=self.inv_var_map,
            linear=linear,
            quadratic=quadratic_sym,
            offset=offset,
            h=h,
            J=J,
            offset_ising=offset_ising
        )

def qubo_cost_vector(qubo: QUBORepresentation) -> np.ndarray:
    """Computes vectorized cost of all 2^N bitstrings.

    Index idx: bit k is ((idx >> k) & 1).
    Used by all solvers to ensure identical objective evaluation.
    """
    n = qubo.n_vars
    dim = 1 << n
    # Vectorized bit matrix: shape (n, dim)
    # bit_matrix[k, idx] = ((idx >> k) & 1)
    indices = np.arange(dim, dtype=np.int64)
    bits = ((indices[:, None] >> np.arange(n)) & 1).astype(float) # shape (dim, n)

    # Cost = offset + bits @ linear + 0.5 * sum((bits @ Q) * bits, axis=1)
    # For upper triangular / symmetric Q where Q has only off-diagonal couplings:
    # bits @ linear: shape (dim,)
    linear_cost = bits @ qubo.linear

    # quadratic cost: 0.5 * sum_k sum_l x_k x_l Q_kl
    # Using quadratic matrix:
    quad_cost = 0.5 * np.sum((bits @ qubo.quadratic) * bits, axis=1)
    
    return qubo.offset + linear_cost + quad_cost

def ising_to_sparse_pauli_op(qubo: QUBORepresentation) -> SparsePauliOp:
    """Converts Ising Hamiltonian to Qiskit SparsePauliOp with little-endian qubit ordering.

    Qiskit convention: Pauli string character at index (n - 1 - k) acts on qubit k.
    """
    n = qubo.n_vars
    pauli_list = []

    # Linear terms: h_k Z_k
    for k in range(n):
        if abs(qubo.h[k]) > 1e-9:
            # String with 'Z' at qubit k (index n - 1 - k) and 'I' elsewhere
            chars = ['I'] * n
            chars[n - 1 - k] = 'Z'
            pauli_list.append(("".join(chars), qubo.h[k]))

    # Quadratic terms: J_kl Z_k Z_l
    for k in range(n):
        for l in range(k + 1, n):
            if abs(qubo.J[k, l]) > 1e-9:
                chars = ['I'] * n
                chars[n - 1 - k] = 'Z'
                chars[n - 1 - l] = 'Z'
                pauli_list.append(("".join(chars), qubo.J[k, l]))

    if not pauli_list:
        pauli_list.append(("I" * n, 0.0))

    return SparsePauliOp.from_list(pauli_list)
