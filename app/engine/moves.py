"""Plain room names typed as moves (no judge needed).

Typing a room's name is the most common input. The engine answers it directly:
already there, one door away (a move), or further away (which door to take
first, no turn spent). A one-character slip on a nearby room's Chinese name
("冷酷" for 冷库) is read as that room.
"""

from __future__ import annotations

from collections import deque
import re
from typing import Optional

from app.content.loader import World

_ZH_PREFIX = ("回到", "走到", "走去", "前往", "进入", "去", "回", "进", "到")
_EN_PREFIX = ("go back to ", "return to ", "walk to ", "go to ", "back to ", "enter ", "go ", "the ")
_PUNCT = re.compile(r"[\s。，！？!?,.、~…]+")


def _core(text: str) -> str:
    t = text.strip().lower()
    for p in _EN_PREFIX:
        if t.startswith(p):
            t = t[len(p):]
    t = _PUNCT.sub(" ", t).strip()
    for p in _ZH_PREFIX:
        if t.startswith(p) and len(t) > len(p):
            t = t[len(p):]
            break
    if t.endswith("吧") and len(t) > 1:
        t = t[:-1]
    return t.strip()


def _aliases(world: World, scene: str) -> list[str]:
    al = world.scenes[scene].get("aliases", {})
    out = [a.lower() for lang in ("zh", "en") for a in al.get(lang, [])]
    out += [n.lower() for n in world.scenes[scene].get("name", {}).values()]
    return out


def match_scene(text: str, world: World, here: str) -> Optional[str]:
    """Scene id the input names on its own, or None. Ending scenes are left to the rules."""
    core = _core(text)
    if not core:
        return None
    for sid, sc in world.scenes.items():
        if sc.get("ending_scene"):
            continue
        if core in _aliases(world, sid):
            return sid
    # One-character slip on a room next door (Chinese names only).
    if 2 <= len(core) <= 5 and not core.isascii():
        for sid in world.scenes[here].get("exits", []):
            if world.scenes[sid].get("ending_scene"):
                continue
            for a in _aliases(world, sid):
                if len(a) == len(core) and sum(x != y for x, y in zip(a, core)) == 1:
                    return sid
    return None


def next_hop(world: World, start: str, goal: str) -> Optional[str]:
    """First room to walk to on the shortest way from start to goal."""
    prev: dict[str, str] = {}
    q = deque([start])
    seen = {start}
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        for nxt in world.scenes[cur].get("exits", []):
            if nxt in seen or world.scenes.get(nxt, {}).get("ending_scene"):
                continue
            seen.add(nxt)
            prev[nxt] = cur
            q.append(nxt)
    if goal not in prev:
        return None
    node = goal
    while prev.get(node) != start:
        node = prev[node]
    return node
