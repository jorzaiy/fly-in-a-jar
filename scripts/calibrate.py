"""Calibration script for readout baselines and intensity thresholds (tasks.md 7 & design §5.4).

Iterates over combinations of action categories, scenes, and danger levels,
runs LIF simulations on the connectome, calculates 75th percentile baselines,
intensity quantiles, and option occurrence frequencies, and updates config/brain_map.yaml.

Usage:
    python scripts/calibrate.py [--reps 3] [--write]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys
import time

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.brain.groups import BrainGroups
from app.brain.lif import LIFSimulator, derive_seed

CONFIG_PATH = REPO_ROOT / "config" / "brain_map.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate FlyWire connectome readout thresholds.")
    parser.add_argument("--reps", type=int, default=2, help="Repetitions per (category, scene, danger) combo")
    parser.add_argument("--write", action="store_true", help="Write calibrated baselines back to config/brain_map.yaml")
    args = parser.parse_args()

    print("======================================================================")
    print("      Fly in a Jar — Connectome Readout Threshold Calibration        ")
    print("======================================================================")

    brain_groups = BrainGroups(CONFIG_PATH)
    sim = LIFSimulator()

    categories = ["look", "move", "take", "use", "eat", "smell", "listen", "touch", "attack", "hide", "wait"]
    scenes = ["reception", "corridor", "cold_storage", "server_room", "fly_room"]
    dangers = [0, 1, 2]

    combos = [(c, s, d) for c in categories for s in scenes for d in dangers]
    total_runs = len(combos) * args.reps
    print(f"Total calibration runs: {len(combos)} combos × {args.reps} reps = {total_runs} runs")

    # Storage for spike counts per readout group
    # key: "category.option" -> list of spike counts
    group_spikes: dict[str, list[int]] = defaultdict(list)
    total_readout_spikes: list[int] = []

    # Map out all readout targets
    readout_map: dict[str, list[int]] = {}
    for cat, opts in brain_groups.readout_groups.items():
        for opt, idxs in opts.items():
            readout_map[f"{cat}.{opt}"] = idxs

    t0 = time.perf_counter()
    run_idx = 0

    for rep in range(args.reps):
        for cat, scene, danger in combos:
            run_idx += 1
            if run_idx % 50 == 0 or run_idx == total_runs:
                elapsed = time.perf_counter() - t0
                pct = run_idx / total_runs * 100
                print(f"  [{run_idx}/{total_runs}] ({pct:.1f}%) — {elapsed:.1f}s elapsed...")

            seed = derive_seed(20261110 + rep, run_idx)
            stim = brain_groups.build_stimulus(cat, scene=scene, danger=danger)
            res = sim.simulate(stim, seed=seed)

            run_readout_sum = 0
            for key, idxs in readout_map.items():
                spks = res.spikes_in_group(idxs)
                group_spikes[key].append(spks)
                run_readout_sum += spks

            total_readout_spikes.append(run_readout_sum)

    total_time = time.perf_counter() - t0
    print(f"\nCalibration completed in {total_time:.2f}s (avg {total_time / total_runs * 1000:.1f} ms/run)")
    print()

    # Calculate 75th percentiles (or baseline) for each group
    baselines: dict[str, float] = {}
    print(f"{'Readout Group':<24} {'Min':<6} {'Median':<8} {'p75':<8} {'Max':<8} {'Baseline'}")
    print("-" * 68)

    for key, spk_list in sorted(group_spikes.items()):
        arr = np.array(spk_list, dtype=np.float32)
        p50 = float(np.percentile(arr, 50))
        p75 = float(np.percentile(arr, 75))
        p90 = float(np.percentile(arr, 90))
        p_max = float(np.max(arr))
        p_min = float(np.min(arr))

        # Baseline: 75th percentile, but ensure >= 1.0 to avoid division by zero
        # If p75 is 0, use p90 or max(1.0, p_max * 0.5)
        if p75 > 0.0:
            base_val = round(p75, 1)
        elif p90 > 0.0:
            base_val = round(p90, 1)
        else:
            base_val = max(1.0, round(p_max, 1))

        baselines[key] = base_val
        print(f"{key:<24} {p_min:<6.0f} {p50:<8.1f} {p75:<8.1f} {p_max:<8.0f} {base_val:.1f}")

    # Calculate intensity thresholds from total readout spikes (quantiles 25, 50, 75)
    tot_arr = np.array(total_readout_spikes)
    i0_thresh = float(np.percentile(tot_arr, 25))
    i1_thresh = float(np.percentile(tot_arr, 50))
    i2_thresh = float(np.percentile(tot_arr, 75))

    intensity_thresholds = [round(i0_thresh, 1), round(i1_thresh, 1), round(i2_thresh, 1)]
    print("\n--- Intensity Quantiles (Total Readout Spikes) ---")
    print(f"Intensity 0: < {intensity_thresholds[0]}")
    print(f"Intensity 1: {intensity_thresholds[0]} – {intensity_thresholds[1]}")
    print(f"Intensity 2: {intensity_thresholds[1]} – {intensity_thresholds[2]}")
    print(f"Intensity 3: >= {intensity_thresholds[2]}")
    print()

    # Simulate selection across all runs to verify option distributions (design §5.4: normalized > 1.0)
    print("--- Option Occurrence Distribution (Normalized Spike / Baseline > 1.0) ---")
    category_counts: dict[str, dict[str, int]] = {
        "monster": defaultdict(int),
        "anomaly": defaultdict(int),
        "clue": defaultdict(int),
        "drift": defaultdict(int),
    }

    for i in range(total_runs):
        # 1. Monster
        monster_scores = {
            opt: group_spikes[f"monster.{opt}"][i] / baselines[f"monster.{opt}"]
            for opt in ["attack", "approach", "retreat", "feed"]
        }
        best_monster = max(monster_scores, key=monster_scores.get)
        if monster_scores[best_monster] >= 1.0:
            category_counts["monster"][best_monster] += 1
        else:
            category_counts["monster"]["absent"] += 1

        # 2. Anomaly
        anomaly_scores = {
            opt: group_spikes[f"anomaly.{opt}"][i] / baselines[f"anomaly.{opt}"]
            for opt in ["visual", "sound", "smell", "memory"]
        }
        best_anomaly = max(anomaly_scores, key=anomaly_scores.get)
        if anomaly_scores[best_anomaly] >= 1.0:
            category_counts["anomaly"][best_anomaly] += 1
        else:
            category_counts["anomaly"]["none"] += 1

        # 3. Clue
        clue_score = group_spikes["clue.clue"][i] / baselines["clue.clue"]
        if clue_score >= 1.0:
            category_counts["clue"]["yes"] += 1
        else:
            category_counts["clue"]["no"] += 1

        # 4. Drift
        drift_score = group_spikes["drift.drift"][i] / baselines["drift.drift"]
        if drift_score >= 1.2:  # Drift is intentionally low probability per design §5.4
            category_counts["drift"]["yes"] += 1
        else:
            category_counts["drift"]["no"] += 1

    for cat_name, counts in category_counts.items():
        print(f"[{cat_name.upper()}]")
        for opt_name, count in sorted(counts.items(), key=lambda x: -x[1]):
            pct = count / total_runs * 100
            print(f"  {opt_name:<12}: {count:>4}/{total_runs} ({pct:>5.1f}%)")

    # Update config/brain_map.yaml if requested
    if args.write:
        print("\nUpdating config/brain_map.yaml with calibrated baselines and thresholds...")
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        # Structure baselines by category
        structured_baselines: dict[str, dict[str, float]] = defaultdict(dict)
        for k, v in baselines.items():
            cat, opt = k.split(".", 1)
            structured_baselines[cat][opt] = v

        cfg["baselines"] = dict(structured_baselines)
        cfg["intensity_thresholds"] = intensity_thresholds

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)
        print("✓ config/brain_map.yaml updated successfully.")


if __name__ == "__main__":
    main()
