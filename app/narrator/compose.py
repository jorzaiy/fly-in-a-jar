"""Narrative assembly and brain log formatting (tasks.md 11.3, 11.4, 11.5 & design §7.1, §5.5).

Assembles the per-turn story narrative from selected fragments in strict sequence,
replaces placeholders, formats scene entry lines, and produces the terminal brain log.
"""

from __future__ import annotations

import logging
from typing import Any

from app.content.loader import Content, World
from app.content.schema import tier_for_sync
from app.engine.rules import items_here
from app.engine.state import GameState
from app.judge.base import JudgeCall

from .elements import StoryElements
from .select import select_fragment

log = logging.getLogger("fly.narrator.compose")


def localize_target(target: str, world: World, content: Content, lang: str) -> str:
    """Translate target ID into human-readable name in requested language."""
    if not target or target == "none":
        return ""
    if target == "monster":
        return "虫群" if lang == "zh" else "the swarm"

    if target in world.items:
        return world.items[target].get("name", {}).get(lang, target)
    if target in world.fixtures:
        return world.fixtures[target].get("name", {}).get(lang, target)
    if target in world.scenes:
        return world.scenes[target].get("name", {}).get(lang, target)

    return target


def resolve_fragment_text(
    frag: dict[str, Any],
    state: GameState,
    lang: str,
    target: str | None,
    world: World,
    content: Content,
) -> str:
    """Select appropriate tier text and replace placeholders (design §7.3)."""
    tier = tier_for_sync(state.sync)

    raw_text = ""
    # 1. Tier selection
    if "tiers" in frag and isinstance(frag["tiers"], dict):
        tier_dict = frag["tiers"].get(tier)
        if tier_dict and isinstance(tier_dict, dict) and lang in tier_dict:
            raw_text = tier_dict[lang]
        elif "human" in frag["tiers"] and lang in frag["tiers"]["human"]:
            raw_text = frag["tiers"]["human"][lang]

    if not raw_text:
        raw_text = frag.get(lang, "")

    # 2. Replace {target} placeholder
    if "{target}" in raw_text:
        localized = localize_target(target or "", world, content, lang)
        raw_text = raw_text.replace("{target}", localized)

    return raw_text.strip()


def format_brain_log(
    judge_call: JudgeCall,
    elements: StoryElements,
    category: str,
    scene: str,
    state: GameState,
    lang: str,
) -> list[dict[str, str]]:
    """Format brain activity log lines in dark-green monospace (design §5.5)."""
    if not state.brainlog:
        return []

    lines: list[dict[str, str]] = []
    res = judge_call.result

    # 1. [JUDGE] line
    if res:
        j_line = (
            f"[JUDGE] feasible {int(res.feasible * 100)}% · "
            f"reason={res.reason} · danger {res.danger}/3 · sync {state.sync}%"
        )
        lines.append({"kind": "brainlog", "text": j_line})

    # 2. [BRAIN] stimulus line
    stim_text = f"stimulus  pathway={category} · scene={scene}"
    lines.append({"kind": "brainlog", "text": f"[BRAIN] {stim_text}"})

    # 3. [BRAIN] spikes line
    spk = elements.spikes
    spk_parts = [
        f"GF {spk.get('monster.attack', 0)}",
        f"P9 {spk.get('monster.approach', 0)}",
        f"MDN {spk.get('monster.retreat', 0)}",
        f"MN9 {spk.get('monster.feed', 0)}",
        f"LC {spk.get('anomaly.visual', 0)}",
        f"MBON {spk.get('anomaly.memory', 0)}",
        f"PAM {spk.get('clue.clue', 0)}",
        f"EPG {spk.get('drift.drift', 0)}",
    ]
    lines.append({"kind": "brainlog", "text": f"[BRAIN] spikes    {' · '.join(spk_parts)}"})

    # 4. [BRAIN] decided line
    monster_decided = elements.monster.upper()
    if elements.monster_override:
        monster_decided = f"{elements.raw_monster.upper()}→{elements.monster.upper()} ({elements.monster_override})"

    anom_decided = f"{elements.anomaly.upper()}({elements.intensity})" if elements.anomaly != "none" else "none"
    clue_decided = f"YES(#{elements.clue_id})" if elements.clue_id else ("YES" if elements.clue_yes else "no")
    drift_decided = "YES" if elements.drift else "no"

    decided_text = (
        f"[BRAIN] decided   monster={monster_decided}  "
        f"anomaly={anom_decided}  clue={clue_decided}  drift={drift_decided}"
    )
    lines.append({"kind": "brainlog", "text": decided_text})

    # 5. [HOST] line at high sync (>= 50%)
    if state.sync >= 50 and (state.turn % 3 == 0 or elements.drift):
        lines.append({
            "kind": "brainlog",
            "text": f"[HOST] synaptic fusion active · somatic facet {state.sync}% · host response observed",
        })

    return lines


def compose_turn(
    elements: StoryElements,
    judge_call: JudgeCall,
    state: GameState,
    world: World,
    content: Content,
    *,
    rule_triggered: str | None = None,
    rule_clue_id: int | None = None,
    hijacked_action: str | None = None,
    moved_scene: str | None = None,
    took: str | None = None,
    target: str | None = None,
    lang: str | None = None,
) -> list[dict[str, str]]:
    """Assemble the turn narrative output in sequence (design §7.1)."""
    lang = lang or state.lang
    output: list[dict[str, str]] = []
    intensity = elements.intensity

    # Total spike count used as random modulo seed for deterministic selection
    total_spikes = sum(elements.spikes.values())

    # 1. [劫持片段] (hijack instinct, design §4 step 3)
    if hijacked_action:
        frag = select_fragment("hijack", hijacked_action, intensity, state, content, total_spikes)
        txt = resolve_fragment_text(frag, state, lang, target, world, content)
        output.append({"kind": "hijack", "text": txt})

    # 2. [判定片段] (verdict or action)
    if judge_call.result:
        res = judge_call.result
        if res.feasible < 0.40:
            frag = select_fragment("verdict_fail", res.reason, intensity, state, content, total_spikes)
            txt = resolve_fragment_text(frag, state, lang, target or res.target, world, content)
            output.append({"kind": "verdict", "text": txt})
        elif res.feasible < 0.65:
            frag = select_fragment("verdict_partial", "default", intensity, state, content, total_spikes)
            txt = resolve_fragment_text(frag, state, lang, target or res.target, world, content)
            output.append({"kind": "verdict", "text": txt})
        else:
            # Feasible >= 0.65
            if rule_triggered and (rule_clue_id or state.ended):
                # The clue or ending text narrates this action; no second line.
                pass
            elif rule_triggered:
                frag = select_fragment("item_use", rule_triggered, intensity, state, content, total_spikes)
                txt = resolve_fragment_text(frag, state, lang, target or res.target, world, content)
                output.append({"kind": "action", "text": txt})
            else:
                frag = select_fragment("action", res.category, intensity, state, content, total_spikes)
                txt = resolve_fragment_text(frag, state, lang, target or res.target, world, content)
                output.append({"kind": "action", "text": txt})

    # 2b. Picked-up item, stated plainly so the player knows it worked.
    if took and took in world.items:
        name = world.items[took].get("name", {}).get(lang, took)
        output.append({"kind": "system", "text": f"（获得：{name}）" if lang == "zh" else f"(Taken: {name})"})

    # 3. [物品线索] (clue from item use rule)
    if rule_clue_id:
        frag = select_fragment("clue", f"clue_{rule_clue_id}", intensity, state, content, total_spikes)
        txt = resolve_fragment_text(frag, state, lang, target, world, content)
        output.append({"kind": "clue", "text": txt})

    # 4. [移动片段] (scene_enter + room listing)
    if moved_scene:
        frag = select_fragment("scene_enter", moved_scene, intensity, state, content, total_spikes)
        txt = resolve_fragment_text(frag, state, lang, target, world, content)
        output.append({"kind": "scene", "text": txt})

        # Append room exits and items listing
        sc_info = world.scenes.get(moved_scene, {})
        exits = sc_info.get("exits", [])
        exit_names = [world.scenes[e]["name"][lang] for e in exits if e in world.scenes]
        here = items_here(state, world)
        items_names = [world.items[it]["name"][lang] for it in here if it in world.items]

        listing_parts = []
        if exit_names:
            exits_title = "出口" if lang == "zh" else "Exits"
            listing_parts.append(f"{exits_title}: {', '.join(exit_names)}")
        if items_names:
            items_title = "可见物品" if lang == "zh" else "Visible items"
            listing_parts.append(f"{items_title}: {', '.join(items_names)}")

        if listing_parts:
            output.append({"kind": "system", "text": " | ".join(listing_parts)})

    # 5. [死寂片段] (silence event, replaces monster & anomaly)
    if elements.silence:
        frag = select_fragment("silence", "default", intensity, state, content, total_spikes)
        txt = resolve_fragment_text(frag, state, lang, target, world, content)
        output.append({"kind": "silence", "text": txt})
    else:
        # 6. [怪物片段]
        if elements.monster != "absent":
            frag = select_fragment("monster", elements.monster, intensity, state, content, elements.spikes.get(f"monster.{elements.monster}", total_spikes))
            txt = resolve_fragment_text(frag, state, lang, target, world, content)
            output.append({"kind": "monster", "text": txt})

        # 7. [异象片段]
        if elements.anomaly != "none":
            frag = select_fragment("anomaly", elements.anomaly, intensity, state, content, elements.spikes.get(f"anomaly.{elements.anomaly}", total_spikes))
            txt = resolve_fragment_text(frag, state, lang, target, world, content)
            output.append({"kind": "anomaly", "text": txt})

        # 8. [线索片段] (fruit fly brain clue discovery)
        if elements.clue_id:
            frag = select_fragment("clue", f"clue_{elements.clue_id}", intensity, state, content, elements.spikes.get("clue.clue", total_spikes))
            txt = resolve_fragment_text(frag, state, lang, target, world, content)
            output.append({"kind": "clue", "text": txt})
            if elements.clue_id not in state.clues_found:
                state.clues_found = [*state.clues_found, elements.clue_id]

    # 9. Brain Log (if enabled)
    cat = judge_call.result.category if judge_call.result else "none"
    brainlog_lines = format_brain_log(judge_call, elements, cat, state.scene, state, lang)
    output.extend(brainlog_lines)

    return output
