"""English state description sent to Jev (design §6.2, tasks.md 10.1).

Scene, exits, visible items, inventory, swarm status, sync, world rules, the
last five actions, and the player's raw input (possibly Chinese) at the end.
Ids are given next to names so the `target` answer can be one of the options.
"""

from __future__ import annotations

from app.content.loader import World
from app.engine.rules import items_here
from app.engine.state import GameState


def _swarm(state: GameState) -> str:
    if state.monster_stunned:
        return f"stunned by CO2 for {state.monster_stunned} more turn(s)"
    if state.monster_block:
        return f"held back for {state.monster_block} more turn(s)"
    return "close by, in this room" if state.monster_near else "not in this room (heard in the walls)"


def state_text(state: GameState, world: World, player_input: str) -> str:
    scene = world.scenes[state.scene]
    en = lambda i: world.name(i, "en")  # noqa: E731
    lines: list[str] = []
    lines.append(f"LOCATION: {en(state.scene)} [{state.scene}]")
    lines.append(f"POWER: {'on' if state.has_flag('power_on') else 'off (emergency lights only)'}")

    exits = []
    for ex in scene.get("exits", []):
        if world.scenes[ex].get("ending_scene"):
            exits.append(f"{en(ex)} [{ex}] (locked revolving door: keycard + power needed)")
        else:
            exits.append(f"{en(ex)} [{ex}]")
    lines.append("EXITS: " + ("; ".join(exits) if exits else "none"))

    fx = []
    for f in scene.get("fixtures", []):
        d = world.fixtures[f]
        note = f" ({d['note_en']})" if d.get("note_en") else ""
        fx.append(f"{en(f)} [{f}]{note}")
    lines.append("FIXTURES HERE: " + ("; ".join(fx) if fx else "none"))

    here = []
    for i in items_here(state, world):
        c = world.items[i].get("container")
        where = f" (in/on the {en(c)})" if c else ""
        here.append(f"{en(i)} [{i}]{where}")
    lines.append("ITEMS LYING HERE (can be taken): " + ("; ".join(here) if here else "none"))
    lines.append("INVENTORY (carried, can be used): "
                 + ("; ".join(f"{en(i)} [{i}]" for i in state.items) if state.items else "nothing"))

    active = [f for f in world.flags if state.has_flag(f) and f != "power_on"]
    if active:
        lines.append("PLAYER CONDITIONS: " + ", ".join(active))
    lines.append(f"THE SWARM [monster]: {_swarm(state)}")
    lines.append(f"SYNAPTIC SYNC: {state.sync}% (100% = consumed)")

    lines.append("WORLD RULES:")
    lines += [f"- {r}" for r in world.judge_rules_en]

    lines.append("RECENT ACTIONS (oldest first):")
    if state.recent_actions:
        lines += [f"- \"{a.text}\" -> {a.result}" for a in state.recent_actions]
    else:
        lines.append("- none yet")

    lines.append("PLAYER ACTION (verbatim; may be Chinese):")
    lines.append(player_input.strip())
    return "\n".join(lines)
