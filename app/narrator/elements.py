"""Story elements derivation from connectome simulation (tasks.md 11.1 & 9.4).

Maps readout group spikes to story elements (monster behavior with overrides,
anomaly type, clue discovery, spatial drift, intensity tier, and dead silence events).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.brain.groups import BrainGroups
from app.brain.lif import SimulationResult
from app.content.loader import World
from app.engine.state import GameState


@dataclass
class StoryElements:
    """The narrative decisions produced by the fly connectome simulation."""

    raw_monster: str                   # 'attack', 'approach', 'retreat', 'feed', 'absent'
    monster: str                       # Behavior after rules overrides
    monster_override: str | None       # 'blocked', 'stunned', 'not_present', 'vial_fly', or None
    anomaly: str                       # 'visual', 'sound', 'smell', 'memory', 'none'
    clue_yes: bool                     # Whether PAM dopamine threshold was crossed
    clue_id: int | None                # Discovered clue ID (1..13) or None
    drift: bool                        # Central complex EPG heading drift
    intensity: int                     # 0, 1, 2, 3
    silence: bool                      # Dead silence event (all readout options absent)
    spikes: dict[str, int] = field(default_factory=dict)  # Group spike counts for brain log


def derive_story_elements(
    sim_res: SimulationResult,
    brain_groups: BrainGroups,
    state: GameState,
    world: World,
) -> StoryElements:
    """Derive story elements from connectome simulation spikes and game state."""
    cfg = brain_groups.config
    baselines: dict[str, dict[str, float]] = cfg.get("baselines", {})
    intensity_thresholds: list[float] = cfg.get("intensity_thresholds", [0.0, 210.0, 4019.0])

    spikes_recorded: dict[str, int] = {}

    # 1. Monster behavior (GF, P9, MDN, MN9)
    monster_opts = ["attack", "retreat", "approach", "feed"]
    monster_scores: dict[str, float] = {}

    for opt in monster_opts:
        idxs = brain_groups.get_readout_neurons("monster", opt)
        spk = sim_res.spikes_in_group(idxs)
        spikes_recorded[f"monster.{opt}"] = spk
        base = baselines.get("monster", {}).get(opt, 1.0)
        monster_scores[opt] = spk / max(1.0, base)

    best_monster = max(monster_scores, key=monster_scores.get)
    if monster_scores[best_monster] >= 1.0:
        raw_monster = best_monster
    else:
        raw_monster = "absent"

    # Monster overrides in priority order (design §5.4 & tasks.md 9.4):
    # ① monster_block > 0 -> absent
    # ② monster_stunned > 0 -> attack/feed become retreat
    # ③ not monster_present -> attack/feed become approach, retreat becomes absent
    # ④ vial_fly in inventory -> attack becomes approach
    modified_monster = raw_monster
    override_reason: str | None = None

    if state.monster_block > 0:
        if modified_monster != "absent":
            modified_monster = "absent"
            override_reason = "monster_block"
    elif state.monster_stunned > 0:
        if modified_monster in ("attack", "feed"):
            modified_monster = "retreat"
            override_reason = "monster_stunned"
    elif not state.monster_near:
        if modified_monster in ("attack", "feed"):
            modified_monster = "approach"
            override_reason = "not_present"
        elif modified_monster == "retreat":
            modified_monster = "absent"
            override_reason = "not_present"
    elif "vial_fly" in state.items and modified_monster == "attack":
        modified_monster = "approach"
        override_reason = "vial_fly"

    # 2. Anomaly type (LC, sound, smell, MBON)
    anomaly_opts = ["visual", "sound", "smell", "memory"]
    anomaly_scores: dict[str, float] = {}

    for opt in anomaly_opts:
        idxs = brain_groups.get_readout_neurons("anomaly", opt)
        spk = sim_res.spikes_in_group(idxs)
        spikes_recorded[f"anomaly.{opt}"] = spk
        base = baselines.get("anomaly", {}).get(opt, 1.0)
        anomaly_scores[opt] = spk / max(1.0, base)

    best_anomaly = max(anomaly_scores, key=anomaly_scores.get)
    if anomaly_scores[best_anomaly] >= 1.0:
        anomaly = best_anomaly
    else:
        anomaly = "none"

    # 3. Clue (PAM dopamine neurons)
    clue_idxs = brain_groups.get_readout_neurons("clue", "clue")
    clue_spikes = sim_res.spikes_in_group(clue_idxs)
    spikes_recorded["clue.clue"] = clue_spikes
    clue_base = baselines.get("clue", {}).get("clue", 1.0)
    clue_yes = (clue_spikes / max(1.0, clue_base)) >= 1.0

    clue_id: int | None = None
    if clue_yes:
        # Pick undiscovered clue
        found_clues = set(state.clues_found)
        # Clue 13 requires synaptic_sync >= 70 (design §5.4 & tasks.md 8.4)
        available_ids = [
            cid for cid in sorted(world.clues.keys())
            if cid not in found_clues and (cid != 13 or state.sync >= 70)
        ]

        # Prioritize clues belonging to current scene
        scene_clues = [
            cid for cid in available_ids
            if state.scene in world.clues[cid].get("scenes", [])
        ]
        if scene_clues:
            clue_id = scene_clues[0]
        elif available_ids:
            clue_id = available_ids[0]

    # 4. Drift (Central complex EPG compass neurons)
    drift_idxs = brain_groups.get_readout_neurons("drift", "drift")
    drift_spikes = sim_res.spikes_in_group(drift_idxs)
    spikes_recorded["drift.drift"] = drift_spikes
    drift_base = baselines.get("drift", {}).get("drift", 1.0)
    drift_yes = (drift_spikes / max(1.0, drift_base)) >= 1.0

    # 5. Intensity tier (0, 1, 2, 3)
    total_readout = sum(spikes_recorded.values())
    t0 = intensity_thresholds[0] if len(intensity_thresholds) > 0 else 0.0
    t1 = intensity_thresholds[1] if len(intensity_thresholds) > 1 else 200.0
    t2 = intensity_thresholds[2] if len(intensity_thresholds) > 2 else 2000.0

    if total_readout < t1:
        intensity = 0
    elif total_readout < t2:
        intensity = 1
    elif total_readout < (t2 * 2.0):
        intensity = 2
    else:
        intensity = 3

    # 6. Dead silence event (design §5.4):
    # All readout events absent/none
    silence = (
        modified_monster == "absent"
        and anomaly == "none"
        and not clue_yes
        and not drift_yes
    )

    return StoryElements(
        raw_monster=raw_monster,
        monster=modified_monster,
        monster_override=override_reason,
        anomaly=anomaly,
        clue_yes=clue_yes,
        clue_id=clue_id,
        drift=drift_yes,
        intensity=intensity,
        silence=silence,
        spikes=spikes_recorded,
    )
