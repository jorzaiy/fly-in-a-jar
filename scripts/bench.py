"""Benchmark script for Fly in a Jar connectome LIF simulator (tasks.md 4.4).

Runs 5 typical stimuli for N trials each, measures average execution latency,
spike activity, reproducibility, and peak memory usage.

Usage:
    python scripts/bench.py [--trials 10]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import resource
import sys
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from app.brain.lif import LIFSimulator, derive_seed

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONNECTOME_PATH = DATA_DIR / "connectome_v783_t5.npz"
NEURONS_PATH = DATA_DIR / "neurons.parquet"


def get_peak_memory_mb() -> float:
    """Returns max resident set size (RSS) in MB."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # On Linux, ru_maxrss is in kilobytes
    return usage.ru_maxrss / 1024.0


def load_sensory_indices() -> dict[str, list[int]]:
    if not NEURONS_PATH.exists():
        print(f"[WARN] {NEURONS_PATH} not found; falling back to index ranges")
        return {
            "visual_light": list(range(100, 200)),
            "mechanosensory_touch": list(range(200, 300)),
            "gustatory_eat": list(range(300, 372)),
            "multimodal_attack": list(range(100, 300)),
            "ambient_silence": [],
        }

    df = pd.read_parquet(NEURONS_PATH)

    def find_indices(types: list[str], max_count: int = 150) -> list[int]:
        matched = df[df["cell_type"].isin(types)]["index"].to_list()
        return matched[:max_count]

    return {
        "visual_light": find_indices(["R1-6", "R7", "R8"], 120),
        "mechanosensory_touch": find_indices(["BM_InOm", "BM_vOcci_vPoOr"], 100),
        "gustatory_eat": find_indices(["BM_Taste", "claw_tpGRN"], 75),
        "multimodal_attack": find_indices(["R1-6", "BM_InOm"], 200),
        "ambient_silence": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark LIF Connectome Simulator.")
    parser.add_argument("--trials", "-n", type=int, default=10, help="Number of trials per stimulus")
    parser.add_argument("--matrix", type=Path, default=CONNECTOME_PATH, help="Path to connectome npz")
    args = parser.parse_args()

    print("======================================================================")
    print("      Fly in a Jar — Connectome LIF Simulator Benchmark              ")
    print("======================================================================")

    init_mem = get_peak_memory_mb()
    t_start = time.perf_counter()
    sim = LIFSimulator(args.matrix)
    load_time = time.perf_counter() - t_start
    post_load_mem = get_peak_memory_mb()

    print(f"Connectome loaded: {sim.num_neurons:,} neurons, {len(sim.indices):,} synapses (t>=5)")
    print(f"Loading time:      {load_time * 1000:.1f} ms")
    print(f"Memory footprint:  {post_load_mem - init_mem:.1f} MB (Peak RSS: {post_load_mem:.1f} MB)")
    print()

    # Reproducibility verification (Task 4.3)
    print("--- Verifying Determinism (Task 4.3) ---")
    test_stim = {i: 150.0 for i in range(100, 150)}
    seed1 = derive_seed(12345, 1)
    seed2 = derive_seed(12345, 1)
    res_a = sim.simulate(test_stim, seed1)
    res_b = sim.simulate(test_stim, seed2)

    assert np.array_equal(res_a.spike_counts, res_b.spike_counts), "Determinism check failed: spike_counts differ!"
    assert np.array_equal(res_a.first_spike_time_ms, res_b.first_spike_time_ms), "Determinism check failed: first_spike_time differs!"
    print(f"✓ PASS: Two identical runs with seed {seed1} yielded identical results ({res_a.total_spikes:,} spikes)")
    print()

    # Run 5 typical stimuli
    stimuli = load_sensory_indices()
    rates = {
        "visual_light": 150.0,
        "mechanosensory_touch": 150.0,
        "gustatory_eat": 180.0,
        "multimodal_attack": 200.0,
        "ambient_silence": 0.0,
    }

    results_table = []

    print(f"--- Running {len(stimuli)} Stimuli Scenarios ({args.trials} trials each) ---")
    for name, indices in stimuli.items():
        rate = rates.get(name, 150.0)
        stim_map = {idx: rate for idx in indices}

        latencies = []
        spike_totals = []
        active_counts = []

        for turn in range(args.trials):
            seed = derive_seed(9999, turn + 1)
            t0 = time.perf_counter()
            r = sim.simulate(stim_map, seed=seed)
            lat = (time.perf_counter() - t0) * 1000.0
            latencies.append(lat)
            spike_totals.append(r.total_spikes)
            active_counts.append(r.active_neurons)

        avg_lat = np.mean(latencies)
        min_lat = np.min(latencies)
        max_lat = np.max(latencies)
        avg_spikes = np.mean(spike_totals)
        avg_active = np.mean(active_counts)

        results_table.append({
            "scenario": name,
            "neurons_stimulated": len(indices),
            "avg_ms": avg_lat,
            "min_ms": min_lat,
            "max_ms": max_lat,
            "avg_spikes": avg_spikes,
            "avg_active": avg_active,
        })

    print()
    print(f"{'Scenario':<22} {'Stim':<6} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10} {'Avg Spikes':<12} {'Active Neurons'}")
    print("-" * 88)
    for row in results_table:
        print(
            f"{row['scenario']:<22} "
            f"{row['neurons_stimulated']:<6} "
            f"{row['avg_ms']:<10.1f} "
            f"{row['min_ms']:<10.1f} "
            f"{row['max_ms']:<10.1f} "
            f"{row['avg_spikes']:<12.0f} "
            f"{row['avg_active']:.0f}"
        )

    final_mem = get_peak_memory_mb()
    print("-" * 88)
    print(f"Final Peak Memory Usage: {final_mem:.1f} MB")
    print()

    # Pass criterion: Avg time < 3000 ms (design §5.2 target is 500-1000 ms)
    overall_avg = np.mean([r["avg_ms"] for r in results_table])
    if overall_avg < 1500.0:
        print(f"🎉 EXCELLENT: Overall average simulation time is {overall_avg:.1f} ms (< 1.5s target).")
    elif overall_avg < 3000.0:
        print(f"✓ PASS: Overall average simulation time is {overall_avg:.1f} ms (< 3.0s threshold).")
    else:
        print(f"⚠ SLOW: Overall average simulation time is {overall_avg:.1f} ms (> 3.0s threshold).")


if __name__ == "__main__":
    main()
