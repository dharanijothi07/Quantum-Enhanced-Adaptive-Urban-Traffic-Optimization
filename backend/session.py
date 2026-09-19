"""Lockstep multi-method traffic simulation session."""
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple
from . import config
from .sim import TrafficSimulator, SimMetrics
from .solvers.fixed import FixedTimeSolver
from .solvers.rule_based import RuleBasedSolver
from .controller import RecedingHorizonController

class SimulationSession:
    """Manages 4 identical simulations (Fixed, Rule-Based, Simulated Annealing, QAOA) in lockstep."""
    def __init__(self, seed: int = 42, speed: float = 3.0, view_method: str = "qaoa", corridor_enabled: bool = True):
        self.seed = seed
        self.speed = speed
        self.view_method = view_method
        self.corridor_enabled = corridor_enabled
        self.running: bool = False
        self._init_simulators()

    def _init_simulators(self) -> None:
        """Initializes all 4 simulator instances with identical seed and topology."""
        self.sim_fixed = TrafficSimulator(seed=self.seed)
        self.sim_rule = TrafficSimulator(seed=self.seed)
        self.sim_sa = TrafficSimulator(seed=self.seed)
        self.sim_qaoa = TrafficSimulator(seed=self.seed)

        self.solver_fixed = FixedTimeSolver()
        self.solver_rule = RuleBasedSolver()
        # Initial signal states default to NS green
        initial_plan = {node_id: config.PHASE_NS for node_id in self.sim_fixed.network.intersections}
        self.sim_fixed.apply_signal_plan(initial_plan)
        self.sim_rule.apply_signal_plan(initial_plan)
        self.sim_sa.apply_signal_plan(initial_plan)
        self.sim_qaoa.apply_signal_plan(initial_plan)

    def reset(self, seed: Optional[int] = None, speed: Optional[float] = None,
              view_method: Optional[str] = None, corridor_enabled: Optional[bool] = None) -> None:
        """Resets the entire session."""
        if seed is not None:
            self.seed = seed
        if speed is not None:
            self.speed = speed
        if view_method is not None:
            self.view_method = view_method
        if corridor_enabled is not None:
            self.corridor_enabled = corridor_enabled
        self._init_simulators()

    def set_control(self, action: str, seed: Optional[int] = None, speed: Optional[float] = None,
                    view_method: Optional[str] = None, corridor_enabled: Optional[bool] = None) -> None:
        """Handles REST control commands: start, pause, reset."""
        if seed is not None:
            self.seed = seed
        if speed is not None:
            self.speed = speed
        if view_method is not None:
            self.view_method = view_method
        if corridor_enabled is not None:
            self.corridor_enabled = corridor_enabled

        if action == "start":
            self.running = True
        elif action == "pause":
            self.running = False
        elif action == "reset":
            self.running = False
            self.reset(seed=self.seed, speed=self.speed, view_method=self.view_method, corridor_enabled=self.corridor_enabled)

    def inject_event(self, event_type: str, link_id: Optional[str] = None, factor: float = 2.0,
                     duration_s: int = 120, origin: Optional[str] = None, destination: Optional[str] = None) -> Dict[str, Any]:
        """Injects an identical event across all 4 simulators."""
        for sim in [self.sim_fixed, self.sim_rule, self.sim_sa, self.sim_qaoa]:
            sim.inject_event(
                event_type=event_type,
                link_id=link_id,
                factor=factor,
                duration_s=duration_s,
                origin=origin,
                destination=destination
            )
        return {
            "status": "success",
            "event_type": event_type,
            "link_id": link_id,
            "duration_s": duration_s,
            "t": self.sim_qaoa.time_s
        }

    def _apply_controls(self, time_s: int, is_slot_boundary: bool) -> None:
        """Computes and applies signal decisions across all 4 methods."""
        inter_ids = list(self.sim_fixed.network.intersections.keys())

        # 1. Fixed Baseline (every second evaluates cycle position)
        res_fixed = self.solver_fixed.solve(current_time_s=time_s, intersection_ids=inter_ids)
        self.sim_fixed.apply_signal_plan(res_fixed.assignment)

        # 2. Rule-Based Baseline (actuated every step)
        res_rule = self.solver_rule.solve(
            network=self.sim_rule.network,
            current_time_s=time_s,
            ambulance=self.sim_rule.emergency.state
        )
        self.sim_rule.apply_signal_plan(res_rule.assignment)

        # 3 & 4. Receding Horizon Solvers (SA & QAOA) every SLOT_S seconds
        if is_slot_boundary:
            # Determine corridor biases if enabled
            sa_biases = self.sim_sa.emergency.get_corridor_bias(time_s) if self.corridor_enabled else None
            qaoa_biases = self.sim_qaoa.emergency.get_corridor_bias(time_s) if self.corridor_enabled else None

            res_sa = self.ctrl_sa.solve_step(time_s, emergency_biases=sa_biases)
            self.sim_sa.apply_signal_plan(res_sa.assignment)

            res_qaoa = self.ctrl_qaoa.solve_step(time_s, emergency_biases=qaoa_biases)
            self.sim_qaoa.apply_signal_plan(res_qaoa.assignment)
        else:
            # Hold current slot decisions
            self.sim_sa.apply_signal_plan(self.ctrl_sa.last_applied_plan)
            self.sim_qaoa.apply_signal_plan(self.ctrl_qaoa.last_applied_plan)

    def step_tick(self) -> None:
        """Advances all 4 simulations by 1 simulated second."""
        curr_t = self.sim_qaoa.time_s
        is_slot_boundary = (curr_t % config.SLOT_S == 0)

        self._apply_controls(curr_t, is_slot_boundary)

        self.sim_fixed.step()
        self.sim_rule.step()
        self.sim_sa.step()
        self.sim_qaoa.step()

    def get_active_simulator(self) -> TrafficSimulator:
        """Returns the simulator corresponding to the active view_method."""
        if self.view_method == "fixed":
            return self.sim_fixed
        elif self.view_method == "rule_based":
            return self.sim_rule
        elif self.view_method == "annealing":
            return self.sim_sa
        return self.sim_qaoa

    def get_state_frame(self) -> Dict[str, Any]:
        """Generates structured WebSocket state frame according to Section 9 schema."""
        active_sim = self.get_active_simulator()
        t = active_sim.time_s

        # Signals
        signals: Dict[str, Any] = {}
        for node_id, inter in active_sim.network.intersections.items():
            signals[node_id] = {
                "phase": inter.phase,
                "lost_time": (inter.lost_time_remaining > 0),
                "lost_time_remaining": inter.lost_time_remaining
            }

        # Links
        links: Dict[str, Any] = {}
        for link_id, link in active_sim.network.links.items():
            links[link_id] = {
                "queue": link.queue,
                "in_transit": sum(c for _, c in link.in_transit),
                "capacity": link.effective_capacity,
                "blocked": (link.discharge_blocked or link.effective_capacity == 0),
                "density": round(link.storage_ratio, 3)
            }

        # Pedestrians
        peds: Dict[str, Any] = {}
        for node_id, inter in active_sim.network.intersections.items():
            peds[node_id] = {
                "ns": round(inter.ped_ns, 1),
                "ew": round(inter.ped_ew, 1)
            }

        # Events
        events: List[Dict[str, Any]] = []
        for ev in active_sim.events:
            events.append({
                "id": ev.id,
                "type": ev.type,
                "link_id": ev.link_id,
                "until": ev.end_time,
                "factor": ev.factor
            })

        # Ambulance
        amb = active_sim.emergency.state
        ambulance_data = {
            "active": amb.active,
            "pos": [round(amb.pos_lat, 6), round(amb.pos_lon, 6)] if amb.active else None,
            "route": amb.route_node_ids,
            "current_node_idx": amb.current_node_idx,
            "eta": {k: round(v - t, 1) for k, v in amb.etas.items() if v >= t},
            "elapsed": amb.elapsed_time_s,
            "total_stops": amb.total_stops,
            "finished": amb.finished
        }

        # Active corridor nodes
        corridor_active = active_sim.emergency.get_corridor_active_nodes(t) if self.corridor_enabled else []

        # Metrics for all 4 methods
        m_fixed = self.sim_fixed.get_metrics()
        m_rule = self.sim_rule.get_metrics()
        m_sa = self.sim_sa.get_metrics()
        m_qaoa = self.sim_qaoa.get_metrics()

        metrics = {
            "fixed": asdict(m_fixed),
            "rule_based": asdict(m_rule),
            "annealing": asdict(m_sa),
            "qaoa": asdict(m_qaoa)
        }

        # Optimized plan from last solve
        optimized_plan: Dict[str, List[int]] = {}
        if self.ctrl_qaoa.last_result and self.ctrl_qaoa.last_result.plan_horizon:
            optimized_plan = self.ctrl_qaoa.last_result.plan_horizon

        # Solver details
        last_res = self.ctrl_qaoa.last_result
        if last_res:
            solver_info = {
                "method": "qaoa",
                "qubits": last_res.extra.get("qubits", 18),
                "p": last_res.extra.get("p", config.QAOA_REPS),
                "backend_used": last_res.extra.get("backend_used", "qiskit"),
                "iters": last_res.extra.get("iters", 0),
                "wall_time_s": round(last_res.wall_time_s, 3),
                "best_cost": last_res.extra.get("best_cost", 0.0),
                "exact_cost": last_res.extra.get("exact_cost", 0.0),
                "gap": last_res.extra.get("gap", 0.0),
                "fallback_used": (self.ctrl_qaoa.fallback_count > 0),
                "late_solves": self.ctrl_qaoa.late_solves
            }
        else:
            solver_info = {
                "method": "qaoa",
                "qubits": 18,
                "p": config.QAOA_REPS,
                "backend_used": "qiskit",
                "iters": 0,
                "wall_time_s": 0.0,
                "best_cost": 0.0,
                "exact_cost": 0.0,
                "gap": 0.0,
                "fallback_used": False,
                "late_solves": 0
            }

        return {
            "type": "state",
            "t": t,
            "seed": self.seed,
            "view_method": self.view_method,
            "running": self.running,
            "corridor_enabled": self.corridor_enabled,
            "signals": signals,
            "links": links,
            "peds": peds,
            "events": events,
            "ambulance": ambulance_data,
            "corridor_active": corridor_active,
            "metrics": metrics,
            "optimized_plan": optimized_plan,
            "solver": solver_info
        }
