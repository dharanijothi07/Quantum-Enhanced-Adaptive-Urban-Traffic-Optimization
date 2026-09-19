"""Grid network topology, links, approaches, and NetworkX routing graph."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import networkx as nx
from . import config

@dataclass
class Link:
    """Directed road segment representing an approach or connection."""
    id: str
    from_node: str # intersection id or boundary id
    to_node: str # intersection id or boundary id
    orientation: str # 'NS' or 'EW'
    approach: str # 'N', 'S', 'E', 'W' (approach into to_node) or 'EXIT'
    capacity: int = config.DEFAULT_LINK_CAPACITY
    length_m: float = config.DEFAULT_LINK_LENGTH_M
    free_flow_time_s: int = config.DEFAULT_FREE_FLOW_TIME_S
    is_boundary_entry: bool = False
    is_boundary_exit: bool = False
    arrival_rate: float = config.DEFAULT_ARRIVAL_RATE

    # Dynamic state
    queue: int = 0 # vehicles stopped at the stop line
    in_transit: List[Tuple[int, int]] = field(default_factory=list) # [(arrival_time_step, count)]
    credit: float = 0.0 # fractional discharge credit
    discharge_blocked: bool = False # blocked by accident
    capacity_override: Optional[int] = None # closure or accident capacity reduction
    recent_outflow: int = 0 # vehicles discharged in last 30s

    @property
    def effective_capacity(self) -> int:
        if self.capacity_override is not None:
            return self.capacity_override
        return self.capacity

    @property
    def total_vehicles(self) -> int:
        transit_count = sum(c for _, c in self.in_transit)
        return self.queue + transit_count

    @property
    def storage_ratio(self) -> float:
        eff_cap = self.effective_capacity
        if eff_cap <= 0:
            return 1.0
        return self.total_vehicles / float(eff_cap)

@dataclass
class Intersection:
    """Signalized intersection node with 4 incoming approaches and pedestrian crossings."""
    id: str
    row: int
    col: int
    lat: float
    lon: float
    # Incoming link IDs mapped by approach direction 'N', 'E', 'S', 'W'
    approaches: Dict[str, str] = field(default_factory=dict)
    # Dynamic signal state
    phase: int = config.PHASE_NS # 0 = NS green, 1 = EW green
    lost_time_remaining: int = 0 # > 0 when transitioning
    time_in_phase: int = 0 # seconds current phase has been held
    # Pedestrian waiting counts
    ped_ns: float = 0.0 # pedestrians crossing parallel to NS (served when NS green)
    ped_ew: float = 0.0 # pedestrians crossing parallel to EW (served when EW green)

class TrafficNetwork:
    """Manages road grid geometry, link topology, and routing graph."""
    def __init__(self, rows: int = config.DEFAULT_GRID_ROWS, cols: int = config.DEFAULT_GRID_COLS):
        self.rows = rows
        self.cols = cols
        self.intersections: Dict[str, Intersection] = {}
        self.links: Dict[str, Link] = {}
        self.graph: nx.DiGraph = nx.DiGraph()
        self._build_grid()

    def _build_grid(self) -> None:
        center_lat, center_lon = config.MAP_CENTER
        d_deg = config.GRID_SPACING_DEG

        # 1. Create Intersections
        for r in range(self.rows):
            for c in range(self.cols):
                node_id = f"I{r * self.cols + c}"
                # Row 0 top, Col 0 left
                lat = center_lat + (self.rows - 1 - r) * d_deg - (self.rows - 1) * d_deg / 2.0
                lon = center_lon + c * d_deg - (self.cols - 1) * d_deg / 2.0
                self.intersections[node_id] = Intersection(
                    id=node_id, row=r, col=c, lat=lat, lon=lon
                )

        # 2. Create Internal and Boundary Links
        # Inter-intersection links (North-South vertical, East-West horizontal)
        for r in range(self.rows):
            for c in range(self.cols):
                node_id = f"I{r * self.cols + c}"
                curr_node = self.intersections[node_id]

                # North neighbor (r-1, c)
                if r > 0:
                    north_id = f"I{(r - 1) * self.cols + c}"
                    link_id = f"L_{north_id}_{node_id}" # going South into node_id from North
                    self.links[link_id] = Link(
                        id=link_id, from_node=north_id, to_node=node_id,
                        orientation="NS", approach="N"
                    )
                    curr_node.approaches["N"] = link_id
                else:
                    # Boundary Entry from North
                    b_in = f"B_ENTRY_{node_id}_N"
                    link_id = f"L_{b_in}_{node_id}"
                    self.links[link_id] = Link(
                        id=link_id, from_node=b_in, to_node=node_id,
                        orientation="NS", approach="N", is_boundary_entry=True
                    )
                    curr_node.approaches["N"] = link_id

                    # Boundary Exit to North
                    b_out = f"B_EXIT_{node_id}_N"
                    link_out_id = f"L_{node_id}_{b_out}"
                    self.links[link_out_id] = Link(
                        id=link_out_id, from_node=node_id, to_node=b_out,
                        orientation="NS", approach="EXIT", is_boundary_exit=True,
                        capacity=999999
                    )

                # South neighbor (r+1, c)
                if r < self.rows - 1:
                    south_id = f"I{(r + 1) * self.cols + c}"
                    link_id = f"L_{south_id}_{node_id}" # going North into node_id from South
                    self.links[link_id] = Link(
                        id=link_id, from_node=south_id, to_node=node_id,
                        orientation="NS", approach="S"
                    )
                    curr_node.approaches["S"] = link_id
                else:
                    # Boundary Entry from South
                    b_in = f"B_ENTRY_{node_id}_S"
                    link_id = f"L_{b_in}_{node_id}"
                    self.links[link_id] = Link(
                        id=link_id, from_node=b_in, to_node=node_id,
                        orientation="NS", approach="S", is_boundary_entry=True
                    )
                    curr_node.approaches["S"] = link_id

                    # Boundary Exit to South
                    b_out = f"B_EXIT_{node_id}_S"
                    link_out_id = f"L_{node_id}_{b_out}"
                    self.links[link_out_id] = Link(
                        id=link_out_id, from_node=node_id, to_node=b_out,
                        orientation="NS", approach="EXIT", is_boundary_exit=True,
                        capacity=999999
                    )

                # West neighbor (r, c-1)
                if c > 0:
                    west_id = f"I{r * self.cols + (c - 1)}"
                    link_id = f"L_{west_id}_{node_id}" # going East into node_id from West
                    self.links[link_id] = Link(
                        id=link_id, from_node=west_id, to_node=node_id,
                        orientation="EW", approach="W"
                    )
                    curr_node.approaches["W"] = link_id
                else:
                    # Boundary Entry from West
                    b_in = f"B_ENTRY_{node_id}_W"
                    link_id = f"L_{b_in}_{node_id}"
                    self.links[link_id] = Link(
                        id=link_id, from_node=b_in, to_node=node_id,
                        orientation="EW", approach="W", is_boundary_entry=True
                    )
                    curr_node.approaches["W"] = link_id

                    # Boundary Exit to West
                    b_out = f"B_EXIT_{node_id}_W"
                    link_out_id = f"L_{node_id}_{b_out}"
                    self.links[link_out_id] = Link(
                        id=link_out_id, from_node=node_id, to_node=b_out,
                        orientation="EW", approach="EXIT", is_boundary_exit=True,
                        capacity=999999
                    )

                # East neighbor (r, c+1)
                if c < self.cols - 1:
                    east_id = f"I{r * self.cols + (c + 1)}"
                    link_id = f"L_{east_id}_{node_id}" # going West into node_id from East
                    self.links[link_id] = Link(
                        id=link_id, from_node=east_id, to_node=node_id,
                        orientation="EW", approach="E"
                    )
                    curr_node.approaches["E"] = link_id
                else:
                    # Boundary Entry from East
                    b_in = f"B_ENTRY_{node_id}_E"
                    link_id = f"L_{b_in}_{node_id}"
                    self.links[link_id] = Link(
                        id=link_id, from_node=b_in, to_node=node_id,
                        orientation="EW", approach="E", is_boundary_entry=True
                    )
                    curr_node.approaches["E"] = link_id

                    # Boundary Exit to East
                    b_out = f"B_EXIT_{node_id}_E"
                    link_out_id = f"L_{node_id}_{b_out}"
                    self.links[link_out_id] = Link(
                        id=link_out_id, from_node=node_id, to_node=b_out,
                        orientation="EW", approach="EXIT", is_boundary_exit=True,
                        capacity=999999
                    )

        self.rebuild_graph()

    def rebuild_graph(self) -> nx.DiGraph:
        """Constructs NetworkX DiGraph with travel_time edge weights for shortest path routing."""
        G = nx.DiGraph()
        for link in self.links.values():
            if link.effective_capacity <= 0 or link.discharge_blocked:
                continue # Skip closed/blocked edges in routing graph
            # Edge weight is free flow travel time
            G.add_edge(link.from_node, link.to_node, link_id=link.id, travel_time=link.free_flow_time_s)
        self.graph = G
        return G

    def get_outgoing_links(self, node_id: str) -> List[Link]:
        """Returns all open outgoing links from intersection node_id."""
        out = []
        for link in self.links.values():
            if link.from_node == node_id and link.effective_capacity > 0:
                out.append(link)
        return out

    def get_outgoing_by_direction(self, node_id: str, incoming_approach: str) -> Dict[str, Optional[Link]]:
        """Maps 'through', 'left', 'right' relative turns to outgoing links for an approach."""
        # For an approach into node_id:
        # N approach (coming from North, heading South): Through=S, Left=E, Right=W
        # S approach (coming from South, heading North): Through=N, Left=W, Right=E
        # W approach (coming from West, heading East):  Through=E, Left=N, Right=S
        # E approach (coming from East, heading West):  Through=W, Left=S, Right=N
        turn_map = {
            "N": {"through": "S", "left": "E", "right": "W"},
            "S": {"through": "N", "left": "W", "right": "E"},
            "W": {"through": "E", "left": "N", "right": "S"},
            "E": {"through": "W", "left": "S", "right": "N"},
        }
        res: Dict[str, Optional[Link]] = {"through": None, "left": None, "right": None}
        target_directions = turn_map.get(incoming_approach, {})
        curr = self.intersections.get(node_id)
        if not curr:
            return res

        r, c = curr.row, curr.col
        for turn, dir_target in target_directions.items():
            if dir_target == "N":
                cand_id = f"I{(r - 1) * self.cols + c}" if r > 0 else f"B_EXIT_{node_id}_N"
            elif dir_target == "S":
                cand_id = f"I{(r + 1) * self.cols + c}" if r < self.rows - 1 else f"B_EXIT_{node_id}_S"
            elif dir_target == "W":
                cand_id = f"I{r * self.cols + (c - 1)}" if c > 0 else f"B_EXIT_{node_id}_W"
            elif dir_target == "E":
                cand_id = f"I{r * self.cols + (c + 1)}" if c < self.cols - 1 else f"B_EXIT_{node_id}_E"
            else:
                cand_id = None

            if cand_id:
                link_id = f"L_{node_id}_{cand_id}"
                if link_id in self.links and self.links[link_id].effective_capacity > 0:
                    res[turn] = self.links[link_id]
        return res
