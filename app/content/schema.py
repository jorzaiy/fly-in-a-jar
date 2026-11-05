"""Shared vocabulary: action categories, failure reasons, sync tiers.

Used by the content validator, the rules engine and the judges, so the
fragment keys, the judge's Choice options and the engine never drift apart.
"""

from __future__ import annotations

# design §6.1 `category` Choice options (also the `action.<key>` fragment keys).
CATEGORIES: tuple[str, ...] = (
    "look", "move", "take", "use", "eat", "smell", "listen",
    "touch", "light", "attack", "hide", "wait", "talk", "other",
)

# design §6.1 `reason` Choice options. `feasible` means "no reason to fail".
REASONS: tuple[str, ...] = (
    "physically_impossible", "missing_item", "no_such_target",
    "against_world_rules", "not_an_action", "feasible",
)
FAIL_REASONS: tuple[str, ...] = tuple(r for r in REASONS if r != "feasible")

# Pseudo-targets always offered to the judge besides scene things.
TARGET_MONSTER = "monster"
TARGET_NONE = "none"

# Assimilation tiers (story ch. 4, design §7.3).
TIERS: tuple[str, ...] = ("human", "latent", "instinct")

HIJACK_KEYS: tuple[str, ...] = ("eat", "flinch", "freeze")
MONSTER_KEYS: tuple[str, ...] = ("attack", "approach", "retreat", "feed")
ANOMALY_KEYS: tuple[str, ...] = ("visual", "sound", "smell", "memory")
ENDINGS: tuple[str, ...] = ("escaped", "consumed", "absorbed", "disconnected")

SYNC_MIN, SYNC_MAX = 0, 100


def tier_for_sync(sync: int) -> str:
    """0–30 human, 31–69 latent, 70–100 instinct."""
    if sync >= 70:
        return "instinct"
    if sync >= 31:
        return "latent"
    return "human"
