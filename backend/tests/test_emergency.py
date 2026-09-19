"""Unit tests for Emergency Green Corridor and Session Lockstep (Phase 4 Gate)."""
import pytest
from backend import config
from backend.session import SimulationSession

def test_emergency_corridor_speedup():
    """Verifies ambulance travel time with corridor ON vs OFF across 5 seeded runs."""
    on_wins = 0
    total_runs = 5

    for seed in range(100, 100 + total_runs):
        # Run with corridor ON
        sess_on = SimulationSession(seed=seed, corridor_enabled=True)
        sess_on.inject_event(event_type="ambulance", origin="B_ENTRY_I0_W", destination="B_EXIT_I5_E")
        for _ in range(250):
            sess_on.step_tick()
        time_on = sess_on.sim_qaoa.emergency.state.elapsed_time_s

        # Run with corridor OFF
        sess_off = SimulationSession(seed=seed, corridor_enabled=False)
        sess_off.inject_event(event_type="ambulance", origin="B_ENTRY_I0_W", destination="B_EXIT_I5_E")
        for _ in range(250):
            sess_off.step_tick()
        time_off = sess_off.sim_qaoa.emergency.state.elapsed_time_s

        print(f"Seed {seed}: Corridor ON = {time_on}s, Corridor OFF = {time_off}s")
        if time_on <= time_off:
            on_wins += 1

    win_rate = on_wins / float(total_runs)
    print(f"Corridor Speedup Win Rate: {win_rate * 100:.1f}% ({on_wins}/{total_runs})")
    assert win_rate >= 0.80, f"Win rate below 80%: {win_rate}"

def test_corridor_normal_restoration():
    """Verifies that after the ambulance clears the network, normal control resumes with empty active corridor."""
    sess = SimulationSession(seed=42, corridor_enabled=True)
    sess.inject_event(event_type="ambulance", origin="B_ENTRY_I0_W", destination="B_EXIT_I5_E")

    for _ in range(200):
        sess.step_tick()

    assert sess.sim_qaoa.emergency.state.finished == True
    active_corridor = sess.sim_qaoa.emergency.get_corridor_active_nodes(sess.sim_qaoa.time_s)
    assert len(active_corridor) == 0, "No active corridor nodes should remain after clearing"
    print("PASS: Normal signal control restoration verified.")

def test_headless_300s_session():
    """Runs a 300s multi-method lockstep session with an ambulance and prints travel times."""
    sess = SimulationSession(seed=42, corridor_enabled=True)
    sess.inject_event(event_type="ambulance", origin="B_ENTRY_I0_W", destination="B_EXIT_I5_E")

    for _ in range(300):
        sess.step_tick()

    frame = sess.get_state_frame()
    m = frame["metrics"]
    print("\n--- 300s Multi-Method Emergency Comparison ---")
    for method in ["fixed", "rule_based", "annealing", "qaoa"]:
        amb_time = m[method]["amb_time"]
        stops = m[method]["amb_stops"]
        wait = m[method]["avg_wait"]
        print(f"[{method.upper():<10}] Amb Time: {amb_time}s | Stops: {stops} | Avg Wait: {wait:.2f}s")

    assert m["qaoa"]["amb_time"] is not None
    assert m["fixed"]["amb_time"] is not None
