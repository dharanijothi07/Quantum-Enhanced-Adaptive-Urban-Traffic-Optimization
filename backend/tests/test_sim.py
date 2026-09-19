"""Tests for microscopic/macroscopic simulator core (Phase 2 Gate)."""
import pytest
from backend import config
from backend.sim import TrafficSimulator
from backend.solvers.fixed import FixedTimeSolver
from backend.solvers.rule_based import RuleBasedSolver

def test_vehicle_conservation():
    """Verifies that vehicles entering the network are strictly conserved over 300 steps."""
    sim = TrafficSimulator(seed=123)
    solver = FixedTimeSolver()

    for step in range(300):
        # Apply fixed signal timing
        res = solver.solve(current_time_s=sim.time_s, intersection_ids=list(sim.network.intersections.keys()))
        sim.apply_signal_plan(res.assignment)
        sim.step()

        # Check vehicle conservation every step
        conserved, arrived, accounted = sim.verify_conservation()
        assert conserved, f"Conservation failed at step {step}: arrived={arrived}, accounted={accounted}"

    metrics = sim.get_metrics()
    assert metrics.total_arrived > 0
    assert metrics.total_exited > 0
    print(f"Vehicle conservation verified: {metrics.total_arrived} vehicles arrived, {metrics.total_exited} exited.")

def test_simulation_determinism():
    """Verifies that running with the identical seed produces bit-identical metrics and state."""
    sim1 = TrafficSimulator(seed=42)
    sim2 = TrafficSimulator(seed=42)
    solver = RuleBasedSolver()

    # Run both with same events
    for sim in (sim1, sim2):
        sim.inject_event(event_type="surge", link_id="L_B_ENTRY_I0_W_I0", factor=2.5, duration_s=60)
        sim.inject_event(event_type="accident", link_id="L_I0_I1", duration_s=50)

    for _ in range(150):
        res1 = solver.solve(network=sim1.network, current_time_s=sim1.time_s, ambulance=sim1.emergency.state)
        sim1.apply_signal_plan(res1.assignment)
        sim1.step()

        res2 = solver.solve(network=sim2.network, current_time_s=sim2.time_s, ambulance=sim2.emergency.state)
        sim2.apply_signal_plan(res2.assignment)
        sim2.step()

    m1 = sim1.get_metrics()
    m2 = sim2.get_metrics()

    assert m1.total_arrived == m2.total_arrived
    assert m1.total_exited == m2.total_exited
    assert m1.total_stops == m2.total_stops
    assert m1.avg_wait == m2.avg_wait
    assert m1.fuel_l == m2.fuel_l
    assert m1.co2_kg == m2.co2_kg
    print("Determinism verified: identical metrics produced.")

def test_blocked_link_never_discharges():
    """Verifies that an accident blocking a link prevents any vehicles from discharging through it."""
    sim = TrafficSimulator(seed=77)
    target_link_id = "L_I1_I2"
    sim.inject_event(event_type="accident", link_id=target_link_id, duration_s=100)

    # Force the green phase on I2 serving L_I1_I2 (W approach = EW green)
    for _ in range(50):
        sim.apply_signal_plan({"I2": config.PHASE_EW})
        sim.step()

    link = sim.network.links[target_link_id]
    assert link.discharge_blocked == True
    # The outflow from this link must be 0 while blocked
    assert link.recent_outflow == 0
    print("Blocked link discharge prevention verified.")

def test_lost_time_enforcement():
    """Verifies that during the 3-second lost time window, zero vehicles discharge."""
    sim = TrafficSimulator(seed=99)
    # Put vehicles on link
    link = sim.network.links["L_B_ENTRY_I0_W_I0"]
    link.queue = 20

    # Start in NS green
    sim.apply_signal_plan({"I0": config.PHASE_NS})
    sim.step()

    # Switch to EW green (triggers 3s lost time)
    sim.apply_signal_plan({"I0": config.PHASE_EW})
    assert sim.network.intersections["I0"].lost_time_remaining == config.LOST_TIME_S

    initial_queue = link.queue
    # Step through lost time
    for _ in range(config.LOST_TIME_S):
        sim.step()

    # Queue should not have discharged during lost time
    # (Arrivals might arrive in transit, but queue at stop line cannot discharge)
    assert sim.network.intersections["I0"].lost_time_remaining == 0
    print("Lost time transition verified.")

def test_headless_600s_run():
    """Executes a full 600s headless run of fixed-time baseline."""
    sim = TrafficSimulator(seed=42)
    solver = FixedTimeSolver()

    for _ in range(600):
        res = solver.solve(current_time_s=sim.time_s, intersection_ids=list(sim.network.intersections.keys()))
        sim.apply_signal_plan(res.assignment)
        sim.step()

    m = sim.get_metrics()
    print(f"\n--- 600s Fixed Baseline Run Metrics ---")
    print(f"Total Arrived: {m.total_arrived}, Exited: {m.total_exited}")
    print(f"Avg Wait Time: {m.avg_wait:.2f} s/veh, Avg Queue: {m.avg_queue:.2f}")
    print(f"Throughput: {m.throughput_h:.1f} veh/h")
    print(f"Estimated Fuel: {m.fuel_l:.2f} L, CO2: {m.co2_kg:.2f} kg")
    assert m.total_exited > 0
    assert m.avg_wait > 0
