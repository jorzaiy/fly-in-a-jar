"""Fragment selection and effects execution (tasks.md 11.2 & design §7.2, §7.4).

Filters candidate fragments by preconditions, deduplicates against used fragments,
matches intensity, picks deterministically by spike count modulo, and executes
fragment effects on the GameState.
"""

from __future__ import annotations

import logging
from typing import Any

from app.content.loader import Content, World
from app.content.schema import SYNC_MAX, SYNC_MIN, tier_for_sync
from app.engine.state import GameState

log = logging.getLogger("fly.narrator.select")


def fragment_satisfies_requires(frag: dict[str, Any], state: GameState) -> bool:
    """Check if a fragment's `requires` block is satisfied by current state."""
    req = frag.get("requires")
    if not req:
        return True

    if "scene" in req and req["scene"] != state.scene:
        return False

    if "items" in req:
        for it in req["items"]:
            if it not in state.items:
                return False

    if "flags" in req:
        for fl in req["flags"]:
            if not state.has_flag(fl):
                return False

    if "not_flags" in req:
        for fl in req["not_flags"]:
            if state.has_flag(fl):
                return False

    if "monster_near" in req:
        if bool(req["monster_near"]) != state.monster_near:
            return False

    if "sync_min" in req and state.sync < req["sync_min"]:
        return False

    if "sync_max" in req and state.sync > req["sync_max"]:
        return False

    if "tier" in req and req["tier"] != tier_for_sync(state.sync):
        return False

    return True


def apply_fragment_effects(frag: dict[str, Any], state: GameState) -> None:
    """Execute fragment effects on game state (design §7.4)."""
    eff = frag.get("effects")
    if not eff:
        return

    # 1. Sync modification
    if "sync" in eff:
        delta = int(eff["sync"])
        state.sync = max(SYNC_MIN, min(SYNC_MAX, state.sync + delta))

    # 2. Flag modification
    if "set_flag" in eff:
        state.set_flag(eff["set_flag"])

    if "clear_flag" in eff:
        state.clear_flag(eff["clear_flag"])

    # 3. Item acquisition
    if "give_item" in eff:
        item = eff["give_item"]
        if item not in state.items:
            state.items = [*state.items, item]
        if item not in state.taken:
            state.taken = [*state.taken, item]

    # 4. Monster presence
    if "monster_near" in eff:
        state.monster_near = bool(eff["monster_near"])


def select_fragment(
    category: str,
    key: str,
    intensity: int,
    state: GameState,
    content: Content,
    spike_count: int = 0,
) -> dict[str, Any]:
    """Select a fragment according to design §7.2 algorithm.

    1. Match category and key
    2. Filter by `requires`
    3. Filter out used fragments (recycle if all exhausted)
    4. Match intensity (exact, else closest)
    5. Pick by `spike_count % candidates_count`
    6. Fall back to `<category>.generic` if empty
    7. Execute effects and record fragment ID in `state.used_fragments`
    """
    candidates = content.by_key(category, key)
    eligible = [c for c in candidates if fragment_satisfies_requires(c, state)]

    if not eligible and key != "generic":
        # Fall back to generic for this category
        generics = content.by_key(category, "generic")
        eligible = [c for c in generics if fragment_satisfies_requires(c, state)]

    if not eligible:
        # Ultimate fallback: return any generic or first candidate even if requires failed
        fallback = content.by_key(category, "generic") or candidates
        if fallback:
            chosen = fallback[0]
            apply_fragment_effects(chosen, state)
            state.record_fragment(chosen["id"])
            return chosen
        # Emergency stub
        return {"id": f"{category}_empty", "category": category, "key": key, "en": "...", "zh": "..."}

    # Deduplicate against used fragments in this session
    unused = [c for c in eligible if c["id"] not in state.used_fragments]
    pool = unused if unused else eligible

    # Match intensity
    exact_intensity = [c for c in pool if c.get("intensity") == intensity]
    if exact_intensity:
        intensity_pool = exact_intensity
    else:
        # Closest intensity
        min_dist = min(abs(c.get("intensity", 0) - intensity) for c in pool)
        intensity_pool = [c for c in pool if abs(c.get("intensity", 0) - intensity) == min_dist]

    # Deterministic selection
    idx = abs(spike_count) % len(intensity_pool)
    chosen = intensity_pool[idx]

    # Apply effects and record
    apply_fragment_effects(chosen, state)
    if chosen["id"] not in state.used_fragments:
        state.used_fragments = [*state.used_fragments, chosen["id"]]

    return chosen
