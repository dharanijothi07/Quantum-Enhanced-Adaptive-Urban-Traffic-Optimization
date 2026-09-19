"""QuantumFlow Configuration and System Constants.

All timing, emission, simulation, QUBO, and solver constants are centralized here.
No magic numbers exist elsewhere in the backend.
"""
from dataclasses import dataclass
from typing import Tuple

# --- Grid & Network Topography ---
DEFAULT_GRID_ROWS: int = 2
DEFAULT_GRID_COLS: int = 3
TOTAL_INTERSECTIONS: int = DEFAULT_GRID_ROWS * DEFAULT_GRID_COLS # 6

MAP_CENTER: Tuple[float, float] = (12.9716, 77.5946) # Bengaluru city center default lat/lon
GRID_SPACING_DEG: float = 0.004 # Approximate spatial grid offset in degrees (~440m)

DEFAULT_LINK_CAPACITY: int = 30 # Maximum vehicles stored per link
DEFAULT_LINK_LENGTH_M: float = 200.0 # Physical length of link in meters
DEFAULT_FREE_FLOW_TIME_S: int = 15 # Seconds for vehicle to traverse link at free flow

# --- Signals & Timing ---
SLOT_S: int = 10 # Control interval in simulated seconds
HORIZON_H: int = 3 # Receding horizon lookahead steps (H slots = 30s)
LOST_TIME_S: int = 3 # Lost time (yellow/all-red) on phase transition
MIN_GREEN_S: int = 6 # Minimum green duration enforced for rule-based
RULE_THRESHOLD: int = 3 # Queue difference threshold for actuated switching
FIXED_CYCLE_S: int = 40 # Fixed baseline cycle: 20s NS / 20s EW (including 3s lost time)

# Signal Bit Encodings: 0 = NS Green, 1 = EW Green
PHASE_NS: int = 0
PHASE_EW: int = 1

# --- Traffic Dynamics & Rates ---
SATURATION_FLOW_RATE: float = 0.5 # veh/s saturation discharge rate when green
DEFAULT_ARRIVAL_RATE: float = 0.14 # veh/s Poisson arrival rate on boundary entry links

# Turning probabilities (sum to 1.0)
PROB_THROUGH: float = 0.70
PROB_LEFT: float = 0.15
PROB_RIGHT: float = 0.15

# Pedestrians
PED_ARRIVAL_RATE: float = 0.03 # Poisson pedestrian arrival rate per crossing group / s
PED_SERVICE_RATE: float = 0.30 # Pedestrians crossed per second of green
PED_WEIGHT: float = 3.0 # Equivalent vehicle queue weight per waiting pedestrian

# --- Emission Model (Documented Assumptions) ---
# Note: Results are estimated comparisons under identical assumptions, not absolute measurements.
IDLE_FUEL_L_PER_S: float = 0.9 / 3600.0 # ~0.9 L/h idling fuel consumption per passenger vehicle
STOP_FUEL_L: float = 0.02 # Litres consumed per vehicle stop event
MOVING_FUEL_L_PER_KM: float = 0.07 # 7.0 L/100km fuel consumption when cruising
CO2_KG_PER_L: float = 2.31 # kg CO2 produced per litre of petrol

# --- QUBO / Ising Weights ---
W_WAIT: float = 1.0 # Linear penalty on unserved waiting vehicles
W_THRU: float = 1.2 # Linear reward on served vehicles
W_SWITCH: float = 15.0 # Quadratic penalty on signal switching between slots
W_WAVE: float = 2.0 # Quadratic reward for green wave coordination on active flows
W_SPILL: float = 50.0 # Linear penalty for sending traffic to near-capacity links (>=80%)
W_EMERGENCY: float = 5000.0 # Large linear bias forcing emergency green corridor phase

# --- Solvers & Quantum Parameters ---
QAOA_REPS: int = 2 # p-depth of QAOA ansatz
QAOA_MAXITER: int = 60 # Maximum COBYLA optimization iterations
QAOA_TIME_BUDGET_S: float = 2.0 # Wall-clock optimization timeout per slot
QAOA_TOP_K: int = 20 # Number of high-probability bitstrings to evaluate classically
MAX_QUBITS: int = 18 # Maximum qubits per cluster partition before sequential clustering
SA_STEPS: int = 4000 # Simulated annealing iteration count

# --- Emergency Vehicle (Ambulance) ---
AMBULANCE_SPEED_MS: float = 15.0 # ~54 km/h cruising speed
AMBULANCE_QUEUE_JUMP_FACTOR: float = 0.3 # seconds of queue clearance delay per waiting vehicle
AMBULANCE_MAX_QUEUE_DELAY_S: float = 6.0 # maximum queue clearance delay
PRECLEAR_S: float = 12.0 # Lookahead window start ahead of estimated arrival (seconds)
CLEAR_S: float = 4.0 # Window extension past estimated arrival (seconds)

DEFAULT_AMB_ORIGIN: str = "B_ENTRY_I0_W" # Default west boundary of I0
DEFAULT_AMB_DEST: str = "B_EXIT_I5_E" # Default east boundary of I5
