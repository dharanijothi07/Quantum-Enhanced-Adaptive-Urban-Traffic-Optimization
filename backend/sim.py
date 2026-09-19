"""Macroscopic discrete-vehicle-count traffic simulator."""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from . import config
from .network import TrafficNetwork, Link, Intersection
from .emergency import EmergencyManager, AmbulanceState

@dataclass
class EventRecord:
    id: str
    type: str # "surge", "accident", "closure", "ambulance"
    link_id: Optional[str] = None
    factor: float = 1.0
    start_time: int = 0
    end_time: int = 0
    origin: Optional[str] = None
    destination: Optional[str] = None

@dataclass
class SimMetrics:
    avg_wait: float = 0.0
    avg_queue: float = 0.0
    total_queue: int = 0
    throughput_h: float = 0.0
    fuel_l: float = 0.0
    co2_kg: float = 0.0
    total_arrived: int = 0
    total_exited: int = 0
    total_stops: int = 0
    total_wait_veh_s: float = 0.0
    cleared_stop_line_count: int = 0
    amb_time: Optional[int] = None
    amb_stops: int = 0
    rolling_avg_wait: float = 0.0

class TrafficSimulator:
    """Simulates multi-intersection network traffic dynamics 1 second per step."""
    def __init__(self, seed: int = 42, rows: int = config.DEFAULT_GRID_ROWS, cols: int = config.DEFAULT_GRID_COLS):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.network = TrafficNetwork(rows=rows, cols=cols)
        self.emergency = EmergencyManager(self.network)
        self.time_s: int = 0
        self.events: List[EventRecord] = []
        self.event_counter: int = 0

        # Metrics accumulators
        self.total_arrived: int = 0
        self.total_exited: int = 0
        self.total_stops: int = 0
        self.total_wait_veh_s: float = 0.0
        self.cleared_stop_line_count: int = 0
        self.total_distance_km: float = 0.0

        # Rolling window history (last 60 seconds)
        self.history_wait_veh_s: List[Tuple[int, float]] = [] # (t, wait_veh_s_this_step)
        self.history_cleared: List[Tuple[int, int]] = [] # (t, cleared_this_step)
        self.recent_outflow_history: List[Tuple[int, str, int]] = [] # (t, link_id, count)

    def inject_event(self, event_type: str, link_id: Optional[str] = None, factor: float = 2.0,
                     duration_s: int = 120, origin: Optional[str] = None, destination: Optional[str] = None) -> EventRecord:
        """Injects a dynamic traffic event."""
        self.event_counter += 1
        ev_id = f"ev_{self.event_counter}"
        rec = EventRecord(
            id=ev_id,
            type=event_type,
            link_id=link_id,
            factor=factor,
            start_time=self.time_s,
            end_time=self.time_s + duration_s,
            origin=origin,
            destination=destination
        )
        self.events.append(rec)

        if event_type == "ambulance":
            orig = origin or config.DEFAULT_AMB_ORIGIN
            dest = destination or config.DEFAULT_AMB_DEST
            self.emergency.dispatch(origin=orig, destination=dest)
        elif event_type == "closure" and link_id and link_id in self.network.links:
            self.network.links[link_id].capacity_override = 0
            self.network.rebuild_graph()
            self.emergency.recalculate_route_if_active(self.time_s)
        elif event_type == "accident" and link_id and link_id in self.network.links:
            link = self.network.links[link_id]
            link.discharge_blocked = True
            link.capacity_override = max(1, link.capacity // 2)
            self.network.rebuild_graph()
            self.emergency.recalculate_route_if_active(self.time_s)

        return rec

    def apply_signal_plan(self, plan: Dict[str, int]) -> None:
        """Applies signal control decisions {intersection_id: target_phase}."""
        for inter_id, target_phase in plan.items():
            inter = self.network.intersections.get(inter_id)
            if not inter:
                continue
            if inter.phase != target_phase:
                # Initiate phase transition with lost time
                inter.phase = target_phase
                inter.lost_time_remaining = config.LOST_TIME_S
                inter.time_in_phase = 0
            else:
                inter.time_in_phase += 1

    def step(self) -> None:
        """Advances simulation by 1 second."""
        self.time_s += 1

        # 1. Update Active Events
        active_events = []
        for ev in self.events:
            if self.time_s <= ev.end_time:
                active_events.append(ev)
            else:
                # Revert expired event modifications
                if ev.type == "closure" and ev.link_id and ev.link_id in self.network.links:
                    self.network.links[ev.link_id].capacity_override = None
                    self.network.rebuild_graph()
                    self.emergency.recalculate_route_if_active(self.time_s)
                elif ev.type == "accident" and ev.link_id and ev.link_id in self.network.links:
                    link = self.network.links[ev.link_id]
                    link.discharge_blocked = False
                    link.capacity_override = None
                    self.network.rebuild_graph()
                    self.emergency.recalculate_route_if_active(self.time_s)
        self.events = active_events

        # 2. Update Pedestrian Arrivals & Signals Lost Time
        for inter in self.network.intersections.values():
            # Decrement lost time
            if inter.lost_time_remaining > 0:
                inter.lost_time_remaining -= 1

            # Pedestrian arrivals (Poisson)
            ped_ns_arr = self.rng.poisson(config.PED_ARRIVAL_RATE)
            ped_ew_arr = self.rng.poisson(config.PED_ARRIVAL_RATE)
            inter.ped_ns += ped_ns_arr
            inter.ped_ew += ped_ew_arr

            # Pedestrian service
            if inter.phase == config.PHASE_NS and inter.lost_time_remaining == 0:
                inter.ped_ns = max(0.0, inter.ped_ns - config.PED_SERVICE_RATE)
            elif inter.phase == config.PHASE_EW and inter.lost_time_remaining == 0:
                inter.ped_ew = max(0.0, inter.ped_ew - config.PED_SERVICE_RATE)

        # 3. Vehicle Arrivals at Boundary Entry Links
        for link in self.network.links.values():
            if link.is_boundary_entry:
                rate = link.arrival_rate
                # Check for surge event on this link
                for ev in self.events:
                    if ev.type == "surge" and (ev.link_id is None or ev.link_id == link.id):
                        rate *= ev.factor
                arr_count = self.rng.poisson(rate)
                if arr_count > 0:
                    # Vehicle arrives and enters in-transit FIFO
                    link.in_transit.append((self.time_s + link.free_flow_time_s, arr_count))
                    self.total_arrived += arr_count
                    self.total_distance_km += arr_count * (link.length_m / 1000.0)

        # 4. In-Transit Vehicles Arriving at Stop Line Queues
        for link in self.network.links.values():
            if not link.in_transit:
                continue
            new_transit = []
            for arr_time, count in link.in_transit:
                if self.time_s >= arr_time:
                    # Check available space at stop line queue
                    space = max(0, link.effective_capacity - link.queue)
                    to_queue = min(count, space)
                    link.queue += to_queue
                    spilled = count - to_queue
                    if spilled > 0:
                        new_transit.append((self.time_s + 1, spilled))
                else:
                    new_transit.append((arr_time, count))
            link.in_transit = new_transit

        # 5. Signal Discharge & Turning
        step_cleared = 0
        for inter_id, inter in self.network.intersections.items():
            # Determine green approaches
            green_approaches = ["N", "S"] if inter.phase == config.PHASE_NS else ["E", "W"]
            is_active_green = (inter.lost_time_remaining == 0)

            for app_dir in ["N", "E", "S", "W"]:
                link_id = inter.approaches.get(app_dir)
                if not link_id or link_id not in self.network.links:
                    continue
                link = self.network.links[link_id]

                if app_dir in green_approaches and is_active_green and not link.discharge_blocked:
                    link.credit += config.SATURATION_FLOW_RATE
                    num_to_discharge = math.floor(link.credit)
                    if num_to_discharge > 0:
                        actual_discharged = min(num_to_discharge, link.queue)
                        if actual_discharged > 0:
                            # Route discharged vehicles
                            discharged_count = self._route_discharged(inter_id, app_dir, actual_discharged)
                            link.queue -= discharged_count
                            link.credit -= discharged_count
                            step_cleared += discharged_count
                            self.cleared_stop_line_count += discharged_count
                            self.total_stops += discharged_count # count stopped vehicle that moves
                            self.recent_outflow_history.append((self.time_s, link.id, discharged_count))
                else:
                    link.credit = 0.0 # reset credit on red/blocked

        # 6. Step Emergency Ambulance
        self.emergency.step(self.time_s)

        # 7. Metrics Accounting
        current_step_wait_veh_s = float(sum(link.queue for link in self.network.links.values()))
        self.total_wait_veh_s += current_step_wait_veh_s

        self.history_wait_veh_s.append((self.time_s, current_step_wait_veh_s))
        self.history_cleared.append((self.time_s, step_cleared))
        cutoff = self.time_s - 60
        self.history_wait_veh_s = [h for h in self.history_wait_veh_s if h[0] > cutoff]
        self.history_cleared = [h for h in self.history_cleared if h[0] > cutoff]
        self.recent_outflow_history = [h for h in self.recent_outflow_history if h[0] > self.time_s - 30]

        # Update link recent outflows
        for link in self.network.links.values():
            link.recent_outflow = sum(c for _, l_id, c in self.recent_outflow_history if l_id == link.id)

    def _route_discharged(self, node_id: str, incoming_approach: str, count: int) -> int:
        """Routes discharged vehicles through intersection based on turning probabilities and capacity."""
        outgoing_map = self.network.get_outgoing_by_direction(node_id, incoming_approach)
        
        # Determine available routes
        p_through = config.PROB_THROUGH if outgoing_map["through"] else 0.0
        p_left = config.PROB_LEFT if outgoing_map["left"] else 0.0
        p_right = config.PROB_RIGHT if outgoing_map["right"] else 0.0
        p_sum = p_through + p_left + p_right

        if p_sum <= 0:
            # All outgoing paths blocked/closed
            return 0

        probs = [p_through / p_sum, p_left / p_sum, p_right / p_sum]
        turns = ["through", "left", "right"]
        counts = self.rng.multinomial(count, probs)

        actually_discharged = 0
        for turn_idx, turn_name in enumerate(turns):
            num = counts[turn_idx]
            if num <= 0:
                continue
            target_link = outgoing_map[turn_name]
            if not target_link:
                continue
            
            if target_link.is_boundary_exit:
                # Vehicle exits network
                self.total_exited += num
                actually_discharged += num
            else:
                # Check downstream storage space: queue + in_transit < capacity
                available = max(0, target_link.effective_capacity - target_link.total_vehicles)
                admitted = min(num, available)
                if admitted > 0:
                    target_link.in_transit.append((self.time_s + target_link.free_flow_time_s, admitted))
                    self.total_distance_km += admitted * (target_link.length_m / 1000.0)
                    actually_discharged += admitted

        return actually_discharged

    def get_metrics(self) -> SimMetrics:
        """Computes instantaneous and cumulative performance metrics."""
        total_q = sum(l.queue for l in self.network.links.values())
        avg_q = total_q / float(len(self.network.links))

        # Average waiting time per vehicle
        # = total waiting vehicle-seconds / vehicles that have cleared a stop line (or exited)
        denom = max(1, self.cleared_stop_line_count)
        avg_wait = self.total_wait_veh_s / float(denom)

        # Rolling 60s average wait
        roll_wait = sum(w for _, w in self.history_wait_veh_s)
        roll_cleared = sum(c for _, c in self.history_cleared)
        rolling_avg_wait = roll_wait / float(max(1, roll_cleared))

        # Throughput (vehicles exiting network per hour)
        throughput_h = (self.total_exited / float(max(1, self.time_s))) * 3600.0

        # Estimated Fuel and CO2 (Section 5.6 model)
        # Idling fuel: IDLE_FUEL_L_PER_S * total_wait_veh_s
        # Stop-start fuel: STOP_FUEL_L * total_stops
        # Moving fuel: MOVING_FUEL_L_PER_KM * total_distance_km
        idle_fuel = config.IDLE_FUEL_L_PER_S * self.total_wait_veh_s
        stop_fuel = config.STOP_FUEL_L * self.total_stops
        move_fuel = config.MOVING_FUEL_L_PER_KM * self.total_distance_km
        total_fuel_l = idle_fuel + stop_fuel + move_fuel
        total_co2_kg = total_fuel_l * config.CO2_KG_PER_L

        # Ambulance metrics
        amb_time = self.emergency.state.elapsed_time_s if self.emergency.state.finished else None
        amb_stops = self.emergency.state.total_stops

        return SimMetrics(
            avg_wait=round(avg_wait, 2),
            avg_queue=round(avg_q, 2),
            total_queue=total_q,
            throughput_h=round(throughput_h, 1),
            fuel_l=round(total_fuel_l, 2),
            co2_kg=round(total_co2_kg, 2),
            total_arrived=self.total_arrived,
            total_exited=self.total_exited,
            total_stops=self.total_stops,
            total_wait_veh_s=round(self.total_wait_veh_s, 1),
            cleared_stop_line_count=self.cleared_stop_line_count,
            amb_time=amb_time,
            amb_stops=amb_stops,
            rolling_avg_wait=round(rolling_avg_wait, 2)
        )

    def verify_conservation(self) -> Tuple[bool, int, int]:
        """Verifies total_arrived == total_exited + total_queued + total_in_transit."""
        queued = sum(l.queue for l in self.network.links.values())
        in_transit = sum(sum(c for _, c in l.in_transit) for l in self.network.links.values())
        accounted = self.total_exited + queued + in_transit
        return (self.total_arrived == accounted), self.total_arrived, accounted
