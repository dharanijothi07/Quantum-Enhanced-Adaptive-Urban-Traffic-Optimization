"""Headless Multi-Seed Benchmark CLI and Runner."""
import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
import numpy as np

from . import config
from .session import SimulationSession

def run_single_simulation(seed: int, duration_s: int, corridor_enabled: bool = True, record_frames: bool = False) -> Dict[str, Any]:
    """Runs a full headless multi-method session for a given seed and duration."""
    session = SimulationSession(seed=seed, corridor_enabled=corridor_enabled)
    recorded_frames: List[Dict[str, Any]] = []

    # Inject benchmark scenario events
    # Surge at t=120 for 120s on west entry of I0
    # Accident at t=200 for 90s on link L_I1_I2
    # Ambulance at t=300 from B_ENTRY_I0_W to B_EXIT_I5_E

    qaoa_gaps: List[float] = []
    qaoa_times: List[float] = []
    sa_gaps: List[float] = []

    for step in range(duration_s):
        curr_t = session.sim_qaoa.time_s

        if curr_t == 120:
            session.inject_event(event_type="surge", link_id="L_B_ENTRY_I0_W_I0", factor=2.5, duration_s=120)
        elif curr_t == 200:
            session.inject_event(event_type="accident", link_id="L_I1_I2", duration_s=90)
        elif curr_t == 300:
            session.inject_event(event_type="ambulance", origin="B_ENTRY_I0_W", destination="B_EXIT_I5_E")

        session.step_tick()

        # Track QAOA metrics on slot boundaries
        if curr_t % config.SLOT_S == 0:
            if session.ctrl_qaoa.last_result:
                gap = session.ctrl_qaoa.last_result.extra.get("gap", 0.0)
                wt = session.ctrl_qaoa.last_result.wall_time_s
                qaoa_gaps.append(gap)
                qaoa_times.append(wt)
            if session.ctrl_sa.last_result:
                sa_gap = session.ctrl_sa.last_result.extra.get("gap", 0.0)
                sa_gaps.append(sa_gap)

        if record_frames and (step % 2 == 0): # Record every 2 simulated seconds (1 frame)
            recorded_frames.append(session.get_state_frame())

    # Collect final metrics
    frame = session.get_state_frame()
    metrics = frame["metrics"]

    res = {
        "seed": seed,
        "duration_s": duration_s,
        "corridor_enabled": corridor_enabled,
        "metrics": metrics,
        "qaoa_solver_stats": {
            "mean_gap": float(np.mean(qaoa_gaps)) if qaoa_gaps else 0.0,
            "mean_wall_time_s": float(np.mean(qaoa_times)) if qaoa_times else 0.0,
            "fallbacks": session.ctrl_qaoa.fallback_count
        }
    }
    if record_frames:
        res["frames"] = recorded_frames
    return res

async def run_benchmark_task(num_seeds: int, duration_s: int, state_dict: Dict[str, Any]):
    """Async wrapper for background execution from REST API."""
    state_dict["status"] = "running"
    state_dict["progress"] = 0
    state_dict["results"] = None

    raw_results = []
    base_seed = 42

    for i in range(num_seeds):
        seed = base_seed + i * 7
        res_on = run_single_simulation(seed, duration_s, corridor_enabled=True)
        res_off = run_single_simulation(seed, duration_s, corridor_enabled=False)
        raw_results.append({"on": res_on, "off": res_off})
        state_dict["progress"] = int(((i + 1) / num_seeds) * 100)
        await asyncio.sleep(0.01)

    summary = aggregate_benchmark_results(raw_results, num_seeds, duration_s)
    state_dict["results"] = summary
    state_dict["status"] = "completed"

    # Save to results/benchmark.json
    out_dir = os.path.join(os.path.dirname(__file__), "..", "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "benchmark.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

def aggregate_benchmark_results(raw_runs: List[Dict[str, Any]], num_seeds: int, duration_s: int) -> Dict[str, Any]:
    """Computes mean +/- std and percent improvements vs fixed baseline."""
    methods = ["fixed", "rule_based", "annealing", "qaoa"]
    metric_keys = ["avg_wait", "avg_queue", "throughput_h", "fuel_l", "co2_kg", "amb_time"]

    aggregated: Dict[str, Any] = {
        "metadata": {
            "num_seeds": num_seeds,
            "duration_s": duration_s,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "methods": {},
        "ambulance_corridor_comparison": {},
        "raw_seeds": []
    }

    # Aggregate corridor ON metrics
    for m in methods:
        agg_m: Dict[str, Any] = {}
        for k in metric_keys:
            vals = []
            for item in raw_runs:
                val = item["on"]["metrics"][m].get(k)
                if val is not None:
                    vals.append(float(val))
            if vals:
                mean_v = float(np.mean(vals))
                std_v = float(np.std(vals))
                agg_m[k] = {
                    "mean": round(mean_v, 2),
                    "std": round(std_v, 2)
                }
            else:
                agg_m[k] = {"mean": None, "std": None}
        aggregated["methods"][m] = agg_m

    # Compute percent changes vs fixed baseline
    fixed_wait = aggregated["methods"]["fixed"]["avg_wait"]["mean"] or 1.0
    fixed_q = aggregated["methods"]["fixed"]["avg_queue"]["mean"] or 1.0
    fixed_thru = aggregated["methods"]["fixed"]["throughput_h"]["mean"] or 1.0
    fixed_fuel = aggregated["methods"]["fixed"]["fuel_l"]["mean"] or 1.0

    for m in methods:
        m_wait = aggregated["methods"][m]["avg_wait"]["mean"]
        m_q = aggregated["methods"][m]["avg_queue"]["mean"]
        m_thru = aggregated["methods"][m]["throughput_h"]["mean"]
        m_fuel = aggregated["methods"][m]["fuel_l"]["mean"]

        aggregated["methods"][m]["pct_improvement"] = {
            "wait_time_pct": round(((fixed_wait - m_wait) / fixed_wait) * 100.0, 1) if m_wait else 0.0,
            "queue_pct": round(((fixed_q - m_q) / fixed_q) * 100.0, 1) if m_q else 0.0,
            "throughput_pct": round(((m_thru - fixed_thru) / fixed_thru) * 100.0, 1) if m_thru else 0.0,
            "fuel_pct": round(((fixed_fuel - m_fuel) / fixed_fuel) * 100.0, 1) if m_fuel else 0.0
        }

    # Ambulance corridor comparison (ON vs OFF)
    for m in ["rule_based", "annealing", "qaoa"]:
        times_on = [item["on"]["metrics"][m]["amb_time"] for item in raw_runs if item["on"]["metrics"][m]["amb_time"] is not None]
        times_off = [item["off"]["metrics"][m]["amb_time"] for item in raw_runs if item["off"]["metrics"][m]["amb_time"] is not None]
        mean_on = float(np.mean(times_on)) if times_on else 0.0
        mean_off = float(np.mean(times_off)) if times_off else 0.0
        pct_speedup = round(((mean_off - mean_on) / max(1.0, mean_off)) * 100.0, 1)
        aggregated["ambulance_corridor_comparison"][m] = {
            "mean_time_corridor_on_s": round(mean_on, 1),
            "mean_time_corridor_off_s": round(mean_off, 1),
            "pct_speedup": pct_speedup
        }

    # QAOA Solver stats
    qaoa_gaps = [item["on"]["qaoa_solver_stats"]["mean_gap"] for item in raw_runs]
    qaoa_wtimes = [item["on"]["qaoa_solver_stats"]["mean_wall_time_s"] for item in raw_runs]
    aggregated["qaoa_summary"] = {
        "mean_optimality_gap": round(float(np.mean(qaoa_gaps)), 4) if qaoa_gaps else 0.0,
        "mean_wall_time_s": round(float(np.mean(qaoa_wtimes)), 3) if qaoa_wtimes else 0.0
    }

    # Raw seed summary
    for idx, item in enumerate(raw_runs):
        aggregated["raw_seeds"].append({
            "seed": item["on"]["seed"],
            "qaoa_wait": item["on"]["metrics"]["qaoa"]["avg_wait"],
            "fixed_wait": item["on"]["metrics"]["fixed"]["avg_wait"],
            "qaoa_amb_time": item["on"]["metrics"]["qaoa"]["amb_time"],
            "fixed_amb_time": item["on"]["metrics"]["fixed"]["amb_time"]
        })

    return aggregated

def _json_default(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    return str(obj)

def record_public_replay(out_path: str, duration_s: int = 300, seed: int = 42):
    """Executes a real simulation run and saves recorded frames to public/replay.json."""
    print(f"Recording verified real simulation replay (duration={duration_s}s, seed={seed})...")
    res = run_single_simulation(seed=seed, duration_s=duration_s, corridor_enabled=True, record_frames=True)
    frames = res.get("frames", [])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(frames, f, default=_json_default)
    print(f"Replay successfully written to {out_path} ({len(frames)} frames).")

def main():
    parser = argparse.ArgumentParser(description="QuantumFlow Multi-Seed Benchmark CLI")
    parser.add_argument("--seeds", type=int, default=5, help="Number of random seeds")
    parser.add_argument("--duration", type=int, default=600, help="Simulation duration per run in seconds")
    parser.add_argument("--out", type=str, default="results/benchmark.json", help="Output JSON path")
    parser.add_argument("--fast", action="store_true", help="Fast run (2 seeds, 300s)")
    parser.add_argument("--record-replay", action="store_true", help="Record and write frontend/public/replay.json")
    args = parser.parse_args()

    num_seeds = 2 if args.fast else args.seeds
    duration_s = 300 if args.fast else args.duration

    if args.record_replay:
        replay_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "replay.json")
        record_public_replay(replay_path, duration_s=300, seed=42)
        return

    print(f"=== QuantumFlow Headless Benchmark ===")
    print(f"Seeds: {num_seeds} | Duration: {duration_s}s per run | Scenario: Surge (t=120), Accident (t=200), Ambulance (t=300)")
    print(f"Running across all 4 control methods...")

    raw_runs = []
    base_seed = 42
    start_wall = time.time()

    for i in range(num_seeds):
        s = base_seed + i * 7
        print(f"  [Seed {i+1}/{num_seeds} (seed={s})] Running Corridor ON...", end="", flush=True)
        r_on = run_single_simulation(s, duration_s, corridor_enabled=True)
        print(f" Corridor OFF...", end="", flush=True)
        r_off = run_single_simulation(s, duration_s, corridor_enabled=False)
        print(" Done.")
        raw_runs.append({"on": r_on, "off": r_off})

    total_time = time.time() - start_wall
    results = aggregate_benchmark_results(raw_runs, num_seeds, duration_s)

    # Save output JSON
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    # Print Summary Table
    print("\n" + "=" * 80)
    print(f"{'QUANTUMFLOW BENCHMARK RESULTS SUMMARY (' + str(num_seeds) + ' SEEDS, ' + str(duration_s) + 's)':^80}")
    print("=" * 80)
    print(f"{'Method':<16} | {'Avg Wait (s)':<14} | {'Queue (veh)':<14} | {'Throughput (/h)':<16} | {'Fuel (L)':<12}")
    print("-" * 80)
    for m in ["fixed", "rule_based", "annealing", "qaoa"]:
        d = results["methods"][m]
        w_str = f"{d['avg_wait']['mean']:.2f} +/- {d['avg_wait']['std']:.2f}"
        q_str = f"{d['avg_queue']['mean']:.2f} +/- {d['avg_queue']['std']:.2f}"
        t_str = f"{d['throughput_h']['mean']:.1f} +/- {d['throughput_h']['std']:.1f}"
        f_str = f"{d['fuel_l']['mean']:.2f} +/- {d['fuel_l']['std']:.2f}"
        print(f"{m.upper():<16} | {w_str:<14} | {q_str:<14} | {t_str:<16} | {f_str:<12}")

    print("-" * 80)
    print("PERCENT IMPROVEMENT VS FIXED-TIME BASELINE:")
    for m in ["rule_based", "annealing", "qaoa"]:
        imp = results["methods"][m]["pct_improvement"]
        print(f"  * {m.upper():<12}: Wait Time: {imp['wait_time_pct']:>+5.1f}% | Queue: {imp['queue_pct']:>+5.1f}% | Throughput: {imp['throughput_pct']:>+5.1f}% | Fuel: {imp['fuel_pct']:>+5.1f}%")

    print("-" * 80)
    print("EMERGENCY AMBULANCE CORRIDOR SPEEDUP (ON vs OFF):")
    for m in ["rule_based", "annealing", "qaoa"]:
        amb_info = results["ambulance_corridor_comparison"][m]
        print(f"  * {m.upper():<12}: Corridor ON: {amb_info['mean_time_corridor_on_s']}s | OFF: {amb_info['mean_time_corridor_off_s']}s | Speedup: {amb_info['pct_speedup']:>+5.1f}%")

    print("-" * 80)
    print(f"QAOA Optimization Gap vs Exact: {results['qaoa_summary']['mean_optimality_gap']:.4f} | Mean Solve Time: {results['qaoa_summary']['mean_wall_time_s']:.3f}s")
    print(f"Benchmark completed in {total_time:.1f}s. Saved to {args.out}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
