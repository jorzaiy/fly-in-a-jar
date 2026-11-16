"""Rules engine (design §3, §6.3; tasks.md 9.3).

Pure functions over GameState + World. The judge decides *whether* an action
works; this module decides *what it does*: movement, taking, the item-use rule
table in content/world.yaml, sync changes, countdowns and the four endings.
Nothing here touches the brain or picks text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import yaml

from app.content.loader import REPO_ROOT, World
from app.content.schema import SYNC_MAX, SYNC_MIN, TARGET_MONSTER

from .state import GameState

Verdict = Literal["success", "partial", "fail"]


# --------------------------------------------------------------------- config


@dataclass(frozen=True)
class RulesConfig:
    success_min: float = 0.65
    partial_min: float = 0.40
    partial_sync: int = 3
    fail_sync_base: int = 5
    fail_sync_per_danger: int = 3
    judge_timeout_s: float = 6.0
    judge_daily_limit: int = 5000
    hijack_sync_min: int = 70


def load_rules_config(path: Path | None = None) -> RulesConfig:
    path = path or REPO_ROOT / "config" / "rules.yaml"
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    v, j, h = raw.get("verdict", {}), raw.get("judge", {}), raw.get("hijack", {})
    return RulesConfig(
        success_min=float(v.get("success_min", 0.65)),
        partial_min=float(v.get("partial_min", 0.40)),
        partial_sync=int(v.get("partial_sync", 3)),
        fail_sync_base=int(v.get("fail_sync_base", 5)),
        fail_sync_per_danger=int(v.get("fail_sync_per_danger", 3)),
        judge_timeout_s=float(j.get("timeout_s", 6)),
        judge_daily_limit=int(j.get("daily_limit", 5000)),
        hijack_sync_min=int(h.get("sync_min", 70)),
    )


# --------------------------------------------------------------------- outcome


@dataclass
class ActionOutcome:
    """What one judged action did. The narrator reads this to pick fragments."""

    category: str
    target: str
    verdict: Verdict = "success"
    reason: str = "feasible"          # judge reason, or the engine's when it blocks
    rule_id: Optional[str] = None
    fragment: Optional[tuple[str, str]] = None  # (category, key) to narrate the action
    blocked: bool = False             # judge allowed it but the world did not
    moved_to: Optional[str] = None
    took: Optional[str] = None
    clue: Optional[int] = None
    clue_repeat: bool = False         # the rule's clue was already found before this turn
    ending: Optional[str] = None
    dampen_anomaly: Optional[str] = None
    sync_before: int = 0
    sync_after: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def sync_delta(self) -> int:
        return self.sync_after - self.sync_before


# --------------------------------------------------------------------- small helpers


def classify(p: float, cfg: RulesConfig) -> Verdict:
    if p >= cfg.success_min:
        return "success"
    if p >= cfg.partial_min:
        return "partial"
    return "fail"


def fail_sync(danger: int, cfg: RulesConfig) -> int:
    return cfg.fail_sync_base + max(0, min(3, danger)) * cfg.fail_sync_per_danger


def add_sync(state: GameState, delta: int) -> int:
    """Clamp to 0–100. Returns the change actually applied."""
    before = state.sync
    state.sync = max(SYNC_MIN, min(SYNC_MAX, before + delta))
    return state.sync - before


def tick_countdowns(state: GameState) -> None:
    """Start of every judged turn: monster_block / monster_stunned count down."""
    if state.monster_block > 0:
        state.monster_block -= 1
    if state.monster_stunned > 0:
        state.monster_stunned -= 1


def items_here(state: GameState, world: World) -> list[str]:
    """Items still lying in the current scene."""
    return [
        i for i, d in world.items.items()
        if d.get("location") == state.scene and i not in state.taken and i not in state.items
    ]


def reachable(state: GameState, world: World, item: str) -> bool:
    return item in state.items or item in items_here(state, world)


PERCEPTION = ("look", "listen", "smell")


def is_visible(state: GameState, world: World, target: str) -> bool:
    """The current scene, its fixtures, items lying here, or anything carried."""
    if target in ("none", "", state.scene, TARGET_MONSTER):
        return True
    v = visible_targets(state, world)
    return any(target in xs for xs in v.values())


def visible_targets(state: GameState, world: World) -> dict[str, list[str]]:
    """Everything the player could name right now (feeds the judge's target options)."""
    scene = world.scenes[state.scene]
    return {
        "exits": list(scene.get("exits", [])),
        "items_here": items_here(state, world),
        "fixtures": list(scene.get("fixtures", [])),
        "inventory": list(state.items),
    }


# --------------------------------------------------------------------- rule table


def _conditions_hold(state: GameState, world: World, when: dict[str, Any]) -> bool:
    if "scene" in when and state.scene != when["scene"]:
        return False
    if any(i not in state.items for i in when.get("items", [])):
        return False
    if any(not reachable(state, world, i) for i in when.get("reachable", [])):
        return False
    if any(i in state.items for i in when.get("not_items", [])):
        return False
    if any(not state.has_flag(f) for f in when.get("flags", [])):
        return False
    if any(state.has_flag(f) for f in when.get("not_flags", [])):
        return False
    if "monster_near" in when and state.monster_near != when["monster_near"]:
        return False
    if "swarm_free" in when and swarm_free(state) != when["swarm_free"]:
        return False
    if "sync_min" in when and state.sync < when["sync_min"]:
        return False
    if any(i not in state.taken for i in when.get("taken", [])):
        return False
    if any(i in state.taken for i in when.get("not_taken", [])):
        return False
    return True


def swarm_free(state: GameState) -> bool:
    """Nothing in the way: the swarm is away, held back, or stunned."""
    return (not state.monster_near) or state.monster_block > 0 or state.monster_stunned > 0


def describe(state: GameState, world: World, table: str, ident: str, lang: str) -> Optional[str]:
    """Text from content/descriptions.yaml (`look` or `revisit`).

    The first variant whose `when` holds decides the condition; variants that
    share that same `when` take turns, so a room you pass through often does
    not read the same every time.
    """
    variants = world.descriptions.get(table, {}).get(ident, [])
    first = next((v for v in variants if _conditions_hold(state, world, v.get("when") or {})), None)
    if first is None:
        return None
    pool = [v for v in variants if (v.get("when") or {}) == (first.get("when") or {})]
    pick = pool[state.turn % len(pool)] if len(pool) > 1 else first
    text = pick.get(lang)
    return text.strip() if isinstance(text, str) else None


def match_rule(state: GameState, world: World, category: str, target: str) -> Optional[dict]:
    """First rule (in world.yaml order) whose trigger and conditions match."""
    for rule in world.rules:
        triggered = any(
            category in t.get("actions", []) and target in t.get("targets", [])
            for t in rule.get("trigger", [])
        )
        if triggered and _conditions_hold(state, world, rule.get("when") or {}):
            return rule
    return None


def _apply_rule(state: GameState, world: World, rule: dict, out: ActionOutcome) -> None:
    eff = rule.get("effects") or {}
    out.rule_id = rule["id"]
    out.fragment = world.fragment_key_for_rule(rule)
    out.blocked = bool(eff.get("block"))
    if "sync" in eff:
        add_sync(state, int(eff["sync"]))
    if "take" in eff and eff["take"] not in state.items:
        _take_item(state, eff["take"])
        out.took = eff["take"]
    for f in eff.get("set_flags", []):
        if f == "power_on" and not state.has_flag(f):
            state.power_turn = max(1, state.turn)
        state.set_flag(f)
    for f in eff.get("clear_flags", []):
        state.clear_flag(f)
    for item in eff.get("consume", []):
        state.items = [i for i in state.items if i != item]
    for src, dst in (eff.get("transform") or {}).items():
        state.items = [dst if i == src else i for i in state.items]
        if dst not in state.taken:
            state.taken = [*state.taken, dst]
    if "monster_block" in eff:
        state.monster_block = max(state.monster_block, int(eff["monster_block"]))
    if "monster_stunned" in eff:
        state.monster_stunned = max(state.monster_stunned, int(eff["monster_stunned"]))
    if "monster_near" in eff:
        state.monster_near = bool(eff["monster_near"])
    if "clue" in eff:
        out.clue = int(eff["clue"])
        out.clue_repeat = out.clue in state.clues_found
        if out.clue not in state.clues_found:
            state.clues_found = [*state.clues_found, out.clue]
    if "dampen_anomaly" in eff:
        out.dampen_anomaly = eff["dampen_anomaly"]
    if "ending" in eff:
        out.ending = eff["ending"]
        state.ended = eff["ending"]


def _take_item(state: GameState, item: str) -> None:
    state.items = [*state.items, item]
    if item not in state.taken:
        state.taken = [*state.taken, item]


def apply_action(state: GameState, world: World, category: str, target: str,
                 out: Optional[ActionOutcome] = None) -> ActionOutcome:
    """Run the effect of an action the judge allowed. Mutates `state`."""
    if out is None:
        out = ActionOutcome(category=category, target=target, sync_before=state.sync)

    rule = match_rule(state, world, category, target)
    if rule is not None:
        _apply_rule(state, world, rule, out)
    elif category == "move":
        scene = world.scenes[state.scene]
        if target == state.scene:
            out.notes.append("already here")
        elif target not in scene.get("exits", []):
            out.blocked, out.reason = True, "no_such_target"
        elif world.scenes[target].get("ending_scene"):
            out.blocked, out.reason = True, "against_world_rules"  # locked door
        else:
            state.scene = target
            out.moved_to = target
    elif category == "take" and world.kind(target) == "item":
        if target in state.items:
            out.notes.append("already carried")
        elif target in items_here(state, world):
            _take_item(state, target)
            out.took = target
        else:
            out.blocked, out.reason = True, "no_such_target"
    if out.fragment is None:
        out.fragment = ("action", category)
    out.sync_after = state.sync
    return out


def check_endings(state: GameState) -> Optional[str]:
    """Sync 100 means consumed, unless a rule already ended the game."""
    if state.ended is None and state.sync >= SYNC_MAX:
        state.ended = "consumed"
    return state.ended


def resolve_turn(state: GameState, world: World, *, feasible: float, reason: str,
                 category: str, target: str, danger: int, cfg: RulesConfig) -> ActionOutcome:
    """Design §4 step 5 for one judged action (the hijack and brain steps live elsewhere).

    Advances the turn, ticks countdowns, classifies the verdict, applies effects
    or the failure sync penalty, and checks endings. Mutates `state`.
    """
    if state.ended is not None:
        raise ValueError("game already ended")
    state.turn += 1
    tick_countdowns(state)
    out = ActionOutcome(category=category, target=target, sync_before=state.sync, reason=reason)
    out.verdict = classify(feasible, cfg)
    if out.verdict != "success":
        if match_rule(state, world, category, target) is not None:
            # The world has a rule for exactly this; it decides, not the judge's confidence.
            out.verdict, out.reason = "success", "feasible"
        elif category in PERCEPTION and is_visible(state, world, target):
            out.verdict, out.reason = "success", "feasible"
    if out.verdict == "fail" and category in PERCEPTION:
        # Looking, listening or sniffing never costs sync, even when it makes no sense.
        out.fragment = ("verdict_fail", reason if reason != "feasible" else "generic")
    elif out.verdict == "fail" and reason == "not_an_action":
        # Gibberish or a typo is not a risk the player took; no sync.
        out.fragment = ("verdict_fail", reason)
    elif out.verdict == "fail":
        add_sync(state, fail_sync(danger, cfg))
        out.fragment = ("verdict_fail", reason if reason != "feasible" else "generic")
    else:
        if out.verdict == "partial":
            add_sync(state, cfg.partial_sync)
        apply_action(state, world, category, target, out)
    out.sync_after = state.sync
    ending = check_endings(state)
    if ending and out.ending is None:
        out.ending = ending
    return out


__all__ = [
    "ActionOutcome", "RulesConfig", "add_sync", "apply_action", "check_endings", "classify",
    "describe", "fail_sync", "is_visible", "items_here", "swarm_free", "load_rules_config", "match_rule", "reachable", "resolve_turn",
    "tick_countdowns", "visible_targets", "TARGET_MONSTER",
]
