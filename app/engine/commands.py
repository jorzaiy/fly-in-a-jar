"""System commands (design §4 step 2, tasks.md 9.2).

help look status inventory notes lang brainlog restart: answered directly.
They never advance the turn, never call the judge and never run the brain.
A bare command word is a system command; anything longer ("look at the
logbook") is a game action and goes to the judge.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.content.loader import Content
from app.content.schema import tier_for_sync

from .rules import items_here
from .state import GameState, new_state

# Accepted spellings. Keys are canonical command names.
ALIASES: dict[str, tuple[str, ...]] = {
    "help": ("help", "?", "h", "帮助"),
    "look": ("look", "l", "环顾", "看看四周", "查看四周"),
    "status": ("status", "stat", "状态"),
    "inventory": ("inventory", "inv", "i", "背包", "物品"),
    "notes": ("notes", "clues", "笔记", "线索"),
    "lang": ("lang", "language", "语言"),
    "brainlog": ("brainlog", "大脑日志"),
    "restart": ("restart", "重新开始", "重开"),
}
_LOOKUP = {alias: name for name, aliases in ALIASES.items() for alias in aliases}
TAKES_ARG = {"lang", "brainlog"}


@dataclass
class CommandResult:
    state: GameState
    output: list[dict[str, str]] = field(default_factory=list)
    command: str = ""

    def add(self, kind: str, text: str) -> None:
        self.output.append({"kind": kind, "text": text})


def parse_command(text: str) -> Optional[tuple[str, Optional[str]]]:
    """Return (command, arg) if `text` is a system command, else None."""
    words = text.strip().split()
    if not words or len(words) > 2:
        return None
    name = _LOOKUP.get(words[0].lower())
    if name is None:
        return None
    arg = words[1].lower() if len(words) == 2 else None
    if arg is not None and name not in TAKES_ARG:
        return None  # "look desk" is an action, not the system look
    return name, arg


def describe_scene(state: GameState, content: Content) -> list[str]:
    """System lines for `look` and for entering a scene (exits, items, fixtures)."""
    w, lang, t = content.world, state.lang, content.text
    sep = t("look.list_sep", lang)
    scene = w.scenes[state.scene]
    lines = [t("look.header", lang, scene=w.name(state.scene, lang))]
    exits = []
    for ex in scene.get("exits", []):
        if w.scenes[ex].get("ending_scene"):
            exits.append(t("look.exit_locked", lang))
        else:
            exits.append(w.name(ex, lang))
    lines.append(t("look.exits", lang, exits=sep.join(exits)) if exits else t("look.exits_none", lang))
    here = items_here(state, w)
    lines.append(t("look.items", lang, items=sep.join(w.name(i, lang) for i in here)) if here
                 else t("look.items_none", lang))
    fx = scene.get("fixtures", [])
    if fx:
        lines.append(t("look.fixtures", lang, fixtures=sep.join(w.name(f, lang) for f in fx)))
    return lines


def _status(state: GameState, content: Content) -> list[str]:
    lang, t = state.lang, content.text
    if state.monster_stunned:
        monster = t("status.monster.stunned", lang, n=state.monster_stunned)
    elif state.monster_block:
        monster = t("status.monster.blocked", lang, n=state.monster_block)
    else:
        monster = t("status.monster.near" if state.monster_near else "status.monster.absent", lang)
    lines = [t("status.line", lang, turn=state.turn, sync=state.sync,
               tier=t(f"status.tier.{tier_for_sync(state.sync)}", lang), monster=monster)]
    flags = [f for f in content.world.flags if state.has_flag(f)]
    if flags:
        sep = t("look.list_sep", lang)
        lines.append(t("status.flags", lang, flags=sep.join(t(f"status.flag.{f}", lang) for f in flags)))
    return lines


def run_command(state: GameState, text: str, content: Content,
                new_seed: Callable[[], int] = lambda: secrets.randbelow(2**31)) -> Optional[CommandResult]:
    """Handle `text` if it is a system command; return None if it is a game action."""
    parsed = parse_command(text)
    if parsed is None:
        return None
    name, arg = parsed
    t, w = content.text, content.world
    res = CommandResult(state=state, command=name)
    lang = state.lang

    if name == "help":
        res.add("system", t("help", lang).rstrip())
    elif name == "look":
        for line in describe_scene(state, content):
            res.add("system", line)
    elif name == "status":
        for line in _status(state, content):
            res.add("system", line)
    elif name == "inventory":
        if state.items:
            sep = t("look.list_sep", lang)
            res.add("system", t("inventory.header", lang, items=sep.join(w.name(i, lang) for i in state.items)))
        else:
            res.add("system", t("inventory.empty", lang))
    elif name == "notes":
        if state.clues_found:
            res.add("system", t("notes.header", lang))
            for n in sorted(state.clues_found):
                res.add("system", t("notes.line", lang, n=n, text=w.clues[n][lang]))
        else:
            res.add("system", t("notes.empty", lang))
    elif name == "lang":
        if arg in ("zh", "en"):
            state.lang = arg
            res.add("system", t("lang.switched", arg))
        else:
            res.add("system", t("lang.usage", lang))
    elif name == "brainlog":
        if arg in ("on", "off"):
            state.brainlog = arg == "on"
            res.add("system", t(f"brainlog.{arg}", lang))
        else:
            res.add("system", t("brainlog.usage", lang))
    elif name == "restart":
        res.state = new_state(w, seed=new_seed(), lang=lang)
        res.state.brainlog = state.brainlog
        res.add("system", t("restart.done", lang))
        for line in describe_scene(res.state, content):
            res.add("system", line)
    return res
