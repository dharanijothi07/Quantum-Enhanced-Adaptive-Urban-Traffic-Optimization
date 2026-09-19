"""Emergency Vehicle (Ambulance) Routing, Movement, and Green Corridor Windows."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import networkx as nx
from . import config
from .network import TrafficNetwork, Link

@dataclass
class AmbulanceState:
    active: bool = False
    origin: str = config.DEFAULT_AMB_ORIGIN
    destination: str = config.DEFAULT_AMB_DEST
    route_node_ids: List[str] = field(default_factory=list) # e.g. ["I0", "I1", "I2", "I5"]
    current_node_idx: int = 0
    current_link_id: Optional[str] = None
    pos_lat: float = 0.0
    pos_lon: float = 0.0
    progress_fraction: float = 0.0 # 0.0 (at start of link) to 1.0 (at end/stop line)
    elapsed_time_s: int = 0
    total_stops: int = 0
    cleared_nodes: List[str] = field(default_factory=list)
    finished: bool = False
    etas: Dict[str, float] = field(default_factory=dict) # Node -> estimated arrival time in seconds

class EmergencyManager:
    """Handles dispatch, movement, routing recalculation, and corridor window calculations."""
    def __init__(self, network: TrafficNetwork):
        self.network = network
        self.state = AmbulanceState()

    def dispatch(self, origin: str = config.DEFAULT_AMB_ORIGIN, destination: str = config.DEFAULT_AMB_DEST) -> bool:
        """Dispatches an ambulance from origin to destination."""
        self.network.rebuild_graph()
        
        # Origin and destination could be boundary links or intersection IDs
        # Determine starting node and path in graph
        start_node = origin.replace("L_", "").split("_")[0] if "L_" in origin else origin
        end_node = destination.replace("L_", "").split("_")[-1] if "L_" in destination else destination

        # Normalize to graph nodes
        if start_node.startswith("B_ENTRY_"):
            # The node it leads to
            entry_link = [l for l in self.network.links.values() if l.from_node == start_node]
            if entry_link:
                start_node = entry_link[0].to_node
        if end_node.startswith("B_EXIT_"):
            exit_link = [l for l in self.network.links.values() if l.to_node == end_node]
            if exit_link:
                end_node = exit_link[0].from_node

        try:
            path = nx.shortest_path(self.network.graph, source=start_node, target=end_node, weight="travel_time")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # Fallback direct path along grid
            path = [start_node, end_node] if start_node in self.network.intersections and end_node in self.network.intersections else ["I0", "I1", "I2", "I5"]

        first_node = self.network.intersections[path[0]]
        self.state = AmbulanceState(
            active=True,
            origin=origin,
            destination=destination,
            route_node_ids=path,
            current_node_idx=0,
            pos_lat=first_node.lat,
            pos_lon=first_node.lon - config.GRID_SPACING_DEG / 2.0, # start just west of first node
            progress_fraction=0.0,
            elapsed_time_s=0,
            total_stops=0,
            cleared_nodes=[],
            finished=False
        )
        self.recompute_etas(current_time_s=0)
        return True

    def recalculate_route_if_active(self, current_time_s: int) -> None:
        """Recalculates route from current location if a road closure or accident occurs."""
        if not self.state.active or self.state.finished:
            return

        self.network.rebuild_graph()
        curr_idx = self.state.current_node_idx
        if curr_idx >= len(self.state.route_node_ids):
            return

        curr_node = self.state.route_node_ids[curr_idx]
        target_node = self.state.route_node_ids[-1]

        try:
            remaining_path = nx.shortest_path(self.network.graph, source=curr_node, target=target_node, weight="travel_time")
            self.state.route_node_ids = self.state.route_node_ids[:curr_idx] + remaining_path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass # Keep existing path if no alternate

        self.recompute_etas(current_time_s)

    def recompute_etas(self, current_time_s: int) -> Dict[str, float]:
        """Calculates ETA to each remaining intersection along route."""
        if not self.state.active or self.state.finished:
            self.state.etas = {}
            return {}

        etas: Dict[str, float] = {}
        cum_time = float(current_time_s)
        curr_idx = self.state.current_node_idx
        path = self.state.route_node_ids

        for i in range(curr_idx, len(path)):
            node_id = path[i]
            if i == curr_idx:
                # Remaining time on current segment
                rem_fraction = 1.0 - self.state.progress_fraction
                link_travel = config.DEFAULT_FREE_FLOW_TIME_S * rem_fraction
                cum_time += link_travel
            else:
                prev_node_id = path[i - 1]
                link_id = f"L_{prev_node_id}_{node_id}"
                link = self.network.links.get(link_id)
                travel_s = link.free_flow_time_s if link else config.DEFAULT_FREE_FLOW_TIME_S
                cum_time += travel_s

            # Queue-jump delay at intersection
            inter = self.network.intersections.get(node_id)
            if inter and i < len(path) - 1:
                # Estimate which approach ambulance enters
                next_node_id = path[i + 1]
                # Find queue for the incoming approach
                prev_id = path[i - 1] if i > 0 else None
                queue_len = 0
                if prev_id:
                    in_link_id = f"L_{prev_id}_{node_id}"
                    in_link = self.network.links.get(in_link_id)
                    if in_link:
                        queue_len = in_link.queue
                queue_delay = min(config.AMBULANCE_MAX_QUEUE_DELAY_S, queue_len * config.AMBULANCE_QUEUE_JUMP_FACTOR)
                cum_time += queue_delay

            etas[node_id] = cum_time

        self.state.etas = etas
        return etas

    def step(self, current_time_s: int) -> None:
        """Advances ambulance position along route by 1 simulated second."""
        if not self.state.active or self.state.finished:
            return

        self.state.elapsed_time_s += 1
        curr_idx = self.state.current_node_idx
        path = self.state.route_node_ids

        if curr_idx >= len(path):
            self.state.finished = True
            self.state.active = False
            return

        target_node_id = path[curr_idx]
        target_node = self.network.intersections[target_node_id]

        # Determine link and incoming approach
        if curr_idx == 0:
            # Entering first intersection from west boundary
            approach_dir = "W"
            required_phase = config.PHASE_EW
            start_lat = target_node.lat
            start_lon = target_node.lon - config.GRID_SPACING_DEG
        else:
            prev_node_id = path[curr_idx - 1]
            prev_node = self.network.intersections[prev_node_id]
            start_lat = prev_node.lat
            start_lon = prev_node.lon
            # Movement direction
            if target_node.row > prev_node.row:
                approach_dir = "N" # heading South, entered from North
                required_phase = config.PHASE_NS
            elif target_node.row < prev_node.row:
                approach_dir = "S" # heading North, entered from South
                required_phase = config.PHASE_NS
            elif target_node.col > prev_node.col:
                approach_dir = "W" # heading East, entered from West
                required_phase = config.PHASE_EW
            else:
                approach_dir = "E" # heading West, entered from East
                required_phase = config.PHASE_EW

        # Movement physics: travel along link
        # Free flow link traverse time is config.DEFAULT_FREE_FLOW_TIME_S (15s)
        # Advance progress_fraction
        step_progress = 1.0 / float(config.DEFAULT_FREE_FLOW_TIME_S)
        
        if self.state.progress_fraction < 1.0:
            self.state.progress_fraction = min(1.0, self.state.progress_fraction + step_progress)
            # Update lat/lon interpolation
            frac = self.state.progress_fraction
            self.state.pos_lat = start_lat + frac * (target_node.lat - start_lat)
            self.state.pos_lon = start_lon + frac * (target_node.lon - start_lon)
        else:
            # At stop line of target_node
            # Check signal: is required phase green and NOT in lost time?
            signal_green = (target_node.phase == required_phase and target_node.lost_time_remaining == 0)
            if signal_green:
                # Clear intersection
                self.state.cleared_nodes.append(target_node_id)
                self.state.current_node_idx += 1
                self.state.progress_fraction = 0.0
                if self.state.current_node_idx >= len(path):
                    self.state.finished = True
                    self.state.active = False
            else:
                # Waiting at red light
                self.state.total_stops += 1

        self.recompute_etas(current_time_s)

    def get_corridor_active_nodes(self, current_time_s: int) -> List[str]:
        """Returns intersection IDs whose corridor window covers the current time."""
        if not self.state.active or self.state.finished:
            return []
        
        active = []
        for node_id, eta in self.state.etas.items():
            window_start = eta - config.PRECLEAR_S
            window_end = eta + config.CLEAR_S
            if window_start <= current_time_s <= window_end:
                active.append(node_id)
        return active

    def get_corridor_bias(self, current_time_s: int, horizon_slots: int = config.HORIZON_H) -> Dict[Tuple[str, int], int]:
        """Returns forced phase requirement {(node_id, slot_t): required_phase} for QUBO/control."""
        if not self.state.active or self.state.finished:
            return {}

        biases: Dict[Tuple[str, int], int] = {}
        path = self.state.route_node_ids

        for i, node_id in enumerate(path):
            if node_id not in self.state.etas:
                continue
            eta = self.state.etas[node_id]
            window_start = eta - config.PRECLEAR_S
            window_end = eta + config.CLEAR_S

            # Determine required phase for node_id along route
            if i == 0:
                req_phase = config.PHASE_EW
            else:
                prev_id = path[i - 1]
                prev = self.network.intersections[prev_id]
                curr = self.network.intersections[node_id]
                req_phase = config.PHASE_NS if curr.row != prev.row else config.PHASE_EW

            for t in range(horizon_slots):
                slot_start = current_time_s + t * config.SLOT_S
                slot_end = slot_start + config.SLOT_S
                # If slot overlaps corridor window
                if not (slot_end < window_start or slot_start > window_end):
                    biases[(node_id, t)] = req_phase

        return biases
