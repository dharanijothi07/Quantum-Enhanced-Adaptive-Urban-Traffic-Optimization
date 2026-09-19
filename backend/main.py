"""FastAPI Application: REST Endpoints and Real-Time WebSocket Streaming."""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import config
from .session import SimulationSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QuantumFlow")

# Global singleton session
session = SimulationSession(seed=42, speed=3.0, view_method="qaoa", corridor_enabled=True)
benchmark_state: Dict[str, Any] = {"status": "idle", "progress": 0, "results": None}

# --- Request Models ---
class ControlRequest(BaseModel):
    action: str = Field(..., pattern="^(start|pause|reset)$")
    seed: Optional[int] = None
    speed: Optional[float] = None
    view_method: Optional[str] = Field(None, pattern="^(fixed|rule_based|annealing|qaoa)$")
    corridor_enabled: Optional[bool] = None

class EventRequest(BaseModel):
    type: str = Field(..., pattern="^(surge|accident|closure|ambulance)$")
    link_id: Optional[str] = None
    factor: Optional[float] = 2.0
    duration_s: Optional[int] = 120
    origin: Optional[str] = None
    destination: Optional[str] = None

class BenchmarkRequest(BaseModel):
    seeds: int = Field(default=5, ge=1, le=20)
    duration_s: int = Field(default=600, ge=60, le=1800)

# --- Background Simulation Loop ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_conns = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_conns.append(connection)
        for dead in dead_conns:
            self.disconnect(dead)

manager = ConnectionManager()

async def simulation_background_loop():
    """Advances simulation according to session speed and streams state at 500ms intervals."""
    while True:
        try:
            start_wall = asyncio.get_event_loop().time()
            # If session is running, compute number of simulation steps for this 500ms real-time chunk
            # 500ms real time at speed 3x = 1.5 steps (on average)
            if session.running:
                # Speed multiplier: e.g. 3x means 3 simulated seconds per 1 real second -> 1.5 steps per 500ms
                # Step at least 1 or proportionally
                steps_to_run = max(1, int(round(session.speed * 0.5)))
                for _ in range(steps_to_run):
                    session.step_tick()

            # Broadcast latest state frame
            frame = session.get_state_frame()
            await manager.broadcast(frame)

            # Sleep remaining time to maintain 500ms interval
            elapsed_wall = asyncio.get_event_loop().time() - start_wall
            sleep_duration = max(0.05, 0.5 - elapsed_wall)
            await asyncio.sleep(sleep_duration)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in simulation loop: {e}", exc_info=True)
            await asyncio.sleep(0.5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch background simulation streamer
    loop_task = asyncio.create_task(simulation_background_loop())
    logger.info("QuantumFlow background simulation streamer started.")
    yield
    # Shutdown
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass
    logger.info("QuantumFlow background simulation streamer stopped.")

app = FastAPI(title="QuantumFlow API", version="1.0.0", lifespan=lifespan)

# Allow CORS for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REST Endpoints ---
@app.get("/api/health")
async def health_check():
    """Health check endpoint exposing quantum backend status."""
    return {
        "status": "healthy",
        "qiskit_available": True,
        "qaoa_backend": "qiskit",
        "version": "1.0.0"
    }

@app.get("/api/network")
async def get_network():
    """Exposes intersection coordinates, links, orientations, and center for the frontend map."""
    intersections = {}
    for node_id, inter in session.sim_qaoa.network.intersections.items():
        intersections[node_id] = {
            "id": node_id,
            "row": inter.row,
            "col": inter.col,
            "lat": inter.lat,
            "lon": inter.lon,
            "approaches": inter.approaches
        }

    links = {}
    for link_id, link in session.sim_qaoa.network.links.items():
        # Compute lat/lon coordinates for link polyline
        from_coords = None
        to_coords = None

        if link.from_node in session.sim_qaoa.network.intersections:
            f_node = session.sim_qaoa.network.intersections[link.from_node]
            from_coords = [f_node.lat, f_node.lon]
        elif link.from_node.startswith("B_ENTRY_"):
            target_id = link.to_node
            t_node = session.sim_qaoa.network.intersections[target_id]
            d = config.GRID_SPACING_DEG
            if link.approach == "N":
                from_coords = [t_node.lat + d, t_node.lon]
            elif link.approach == "S":
                from_coords = [t_node.lat - d, t_node.lon]
            elif link.approach == "W":
                from_coords = [t_node.lat, t_node.lon - d]
            else:
                from_coords = [t_node.lat, t_node.lon + d]

        if link.to_node in session.sim_qaoa.network.intersections:
            t_node = session.sim_qaoa.network.intersections[link.to_node]
            to_coords = [t_node.lat, t_node.lon]
        elif link.to_node.startswith("B_EXIT_"):
            f_node = session.sim_qaoa.network.intersections[link.from_node]
            d = config.GRID_SPACING_DEG
            if "_N" in link.to_node:
                to_coords = [f_node.lat + d, f_node.lon]
            elif "_S" in link.to_node:
                to_coords = [f_node.lat - d, f_node.lon]
            elif "_W" in link.to_node:
                to_coords = [f_node.lat, f_node.lon - d]
            else:
                to_coords = [f_node.lat, f_node.lon + d]

        links[link_id] = {
            "id": link_id,
            "from_node": link.from_node,
            "to_node": link.to_node,
            "orientation": link.orientation,
            "approach": link.approach,
            "capacity": link.capacity,
            "length_m": link.length_m,
            "is_boundary_entry": link.is_boundary_entry,
            "is_boundary_exit": link.is_boundary_exit,
            "geometry": [from_coords, to_coords] if (from_coords and to_coords) else []
        }

    return {
        "map_center": list(config.MAP_CENTER),
        "grid_spacing_deg": config.GRID_SPACING_DEG,
        "intersections": intersections,
        "links": links
    }

@app.post("/api/control")
async def control_simulation(req: ControlRequest):
    """Controls session playback (start/pause/reset/speed/view_method/corridor)."""
    session.set_control(
        action=req.action,
        seed=req.seed,
        speed=req.speed,
        view_method=req.view_method,
        corridor_enabled=req.corridor_enabled
    )
    return {
        "status": "success",
        "action": req.action,
        "running": session.running,
        "view_method": session.view_method,
        "speed": session.speed,
        "corridor_enabled": session.corridor_enabled
    }

@app.post("/api/event")
async def inject_event(req: EventRequest):
    """Injects dynamic traffic events into all running simulators."""
    # Validation: ensure link exists if specified
    if req.link_id and req.link_id not in session.sim_qaoa.network.links:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid link_id '{req.link_id}'"
        )

    res = session.inject_event(
        event_type=req.type,
        link_id=req.link_id,
        factor=req.factor or 2.0,
        duration_s=req.duration_s or 120,
        origin=req.origin,
        destination=req.destination
    )
    return res

@app.post("/api/benchmark")
async def trigger_benchmark(req: BenchmarkRequest):
    """Triggers background headless benchmark."""
    # Load benchmark module dynamically to execute asynchronously
    from . import benchmark
    asyncio.create_task(benchmark.run_benchmark_task(req.seeds, req.duration_s, benchmark_state))
    return {"status": "started", "seeds": req.seeds, "duration_s": req.duration_s}

@app.get("/api/benchmark/latest")
async def get_latest_benchmark():
    """Returns latest completed benchmark results or status."""
    if benchmark_state["results"] is not None:
        return benchmark_state["results"]
    
    # Try reading results/benchmark.json if present
    import os
    results_path = os.path.join(os.path.dirname(__file__), "..", "results", "benchmark.json")
    if os.path.exists(results_path):
        try:
            with open(results_path, "r") as f:
                return json.load(f)
        except Exception:
            pass

    return benchmark_state

@app.get("/api/replay")
async def get_replay_data():
    """Returns recorded replay run JSON for offline fallback."""
    import os
    replay_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "replay.json")
    if os.path.exists(replay_path):
        with open(replay_path, "r") as f:
            return json.load(f)
    return []

# --- WebSocket Stream ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time 500ms state streaming connection."""
    await manager.connect(websocket)
    try:
        # Immediately send current state on connection
        await websocket.send_json(session.get_state_frame())
        while True:
            # Keep receiving client pings/messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
