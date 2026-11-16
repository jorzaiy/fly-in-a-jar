"""Per-action readout baselines (relative_baselines in config/brain_map.yaml).

Samples turns the way people play them (mostly moves, looks and takes, in
every room, before and after the power, at a range of sync levels and with
different wording), runs the connectome for each, and records how much each
readout group spikes for each kind of action. A readout then counts as an
event only when it spikes past that action's usual level (a percentile set
per readout below): the event is the brain doing something unusual.

Also prints the giant-fibre (GF) distribution against the swarm drive, which
is what `monster_thresholds` are read from.

Usage:
    python scripts/calibrate_relative.py --runs 400 [--write]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
import random
import sys
import time

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.brain.drive import swarm_drive
from app.brain.groups import BrainGroups
from app.brain.lif import LIFSimulator, derive_seed
from app.engine.state import GameState

CONFIG_PATH = REPO_ROOT / "config" / "brain_map.yaml"

# Share of each action in real play (two playtests, 11-16) and the percentile
# a readout must pass to count as an event.
CATEGORY_WEIGHTS = {"move": 40, "look": 25, "take": 15, "use": 10, "touch": 3, "listen": 2,
                    "smell": 2, "eat": 1, "attack": 1, "light": 1}
PERCENTILE = {"anomaly": 75, "clue": 92, "drift": 95, "monster": 80}
# Anomaly, clue and drift are read against the quiet building (before the
# power), so they show up from the first turns and grow more frequent once the
# swarm wakes and sync climbs. The monster readouts use every sample.
QUIET_ONLY = ("anomaly", "clue", "drift")
FLOOR = 30.0
WORDS = ["门", "灯", "桌子", "照片", "冰柜", "玻片", "她", "机柜", "终端", "管子", "手套", "糖",
         "door", "lamp", "desk", "photo", "freezer", "slide", "rack", "vial", "gloves", "sugar"]
VERBS = ["检查", "看看", "拿", "用", "摸", "听", "闻", "打开", "go to", "look at", "take", "use"]
SCENES = ["reception", "corridor", "fly_room", "prep_room", "em_room", "server_room", "cold_storage"]


def sample_state(rnd: random.Random) -> GameState:
    st = GameState(seed=rnd.randrange(2**62), lang="zh")
    st.scene = rnd.choice(SCENES)
    st.sync = rnd.choice([0, 0, 5, 10, 18, 25, 38, 50, 65, 80])
    st.turn = rnd.randint(5, 70)
    if rnd.random() < 0.5:
        st.set_flag("power_on")
        st.power_turn = max(1, st.turn - rnd.randint(0, 15))
        r = rnd.random()
        if r < 0.1:
            st.monster_block = 2
        elif r < 0.15:
            st.monster_stunned = 2
        elif r < 0.25:
            st.caught_fly = True
    return st


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=400)
    ap.add_argument("--seed", type=int, default=20261116)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dump", default="")
    args = ap.parse_args()

    bg = BrainGroups(CONFIG_PATH)
    sim = LIFSimulator()
    rnd = random.Random(args.seed)
    readouts = {f"{c}.{o}": ix for c, opts in bg.readout_groups.items() for o, ix in opts.items()}
    cats, weights = zip(*CATEGORY_WEIGHTS.items())

    per_cat: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    quiet: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    gf_rows: list[tuple[float, str, int]] = []
    t0 = time.perf_counter()
    for i in range(args.runs):
        st = sample_state(rnd)
        cat = rnd.choices(cats, weights)[0]
        text = f"{rnd.choice(VERBS)} {rnd.choice(WORDS)}"
        hz = swarm_drive(st, bg.config)
        stim = bg.build_stimulus(cat, action_text=text, scene=st.scene, danger=rnd.choice([0, 0, 0, 1]),
                                 input_key=text, swarm_hz=hz, sync=st.sync)
        res = sim.simulate(stim, seed=derive_seed(args.seed, i))
        for key, ix in readouts.items():
            per_cat[cat][key].append(res.spikes_in_group(ix))
            if not st.has_flag("power_on"):
                quiet[cat][key].append(res.spikes_in_group(ix))
        gf_rows.append((hz, cat, res.spikes_in_group(readouts["monster.attack"])))
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{args.runs}  {time.perf_counter() - t0:.0f}s", flush=True)

    rel: dict[str, dict[str, float]] = {}
    for cat, groups in sorted(per_cat.items()):
        if len(next(iter(groups.values()))) < 10:
            continue  # too few samples; the absolute baselines cover it
        rel[cat] = {}
        for key, vals in groups.items():
            kind = key.split(".")[0]
            pct = PERCENTILE[kind]
            base = float(np.percentile(vals, pct))
            if kind in QUIET_ONLY and len(quiet[cat][key]) >= 8:
                # Quiet level, but never below the median over all play or
                # FLOOR spikes: a readout that is silent in the quiet building
                # must not fire on its first stray spike.
                base = max(float(np.percentile(quiet[cat][key], pct)),
                           float(np.percentile(vals, 50)), FLOOR)
            rel[cat][key] = round(max(1.0, base), 1)
        print(cat, len(next(iter(groups.values()))), rel[cat])

    print("\nGF by swarm drive (Hz bucket: mean, p10, p90, n)")
    buckets = defaultdict(list)
    for hz, _cat, gf in gf_rows:
        buckets[int(hz // 15) * 15].append(gf)
    for b in sorted(buckets):
        v = np.array(buckets[b])
        print(f"  {b:>3}-{b + 14:<3} {v.mean():6.1f} {np.percentile(v, 10):6.1f} {np.percentile(v, 90):6.1f} {len(v)}")

    if args.dump:
        Path(args.dump).write_text(json.dumps({"rel": rel, "gf": gf_rows,
                                               "per_cat": {c: dict(g) for c, g in per_cat.items()},
                                               "quiet": {c: dict(g) for c, g in quiet.items()}}))
    if args.write:
        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        # Categories never sampled fall back to the absolute baselines.
        cfg["relative_baselines"] = rel
        CONFIG_PATH.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print("wrote relative_baselines")


if __name__ == "__main__":
    main()
