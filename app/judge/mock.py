"""Keyword mock judge (tasks.md 10.3). Used with JUDGE=mock and in tests.

Deterministic: the same state and text always give the same answer. It reads
zh and en keywords to find the action category and the things mentioned, then
checks them against the scene, the inventory and world.yaml, and answers the
five questions of design §6.1 exactly like the real judge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.content.loader import World
from app.content.schema import TARGET_MONSTER, TARGET_NONE
from app.engine.rules import items_here
from app.engine.state import GameState

from .base import Judge, JudgeResult, normalize, target_options

# ------------------------------------------------------------------ keyword tables
# Each entry: (zh substrings, en regexes). English matching is on word boundaries.

IMPOSSIBLE = (
    ("飞出", "飞起", "飞到", "飞走", "飞上", "飞过", "起飞", "瞬移", "传送", "穿墙", "穿过墙", "隐身", "时间倒流"),
    (r"\bfly (out|away|up|off|over|through|to|into|across)\b", r"\bteleport", r"\blevitate",
     r"\bwalk through (the )?walls?\b", r"\bturn invisible\b", r"\bgo back in time\b"),
)
NOT_ACTION = (
    ("你好", "谢谢", "为什么", "是谁", "什么是"),
    (r"^(hi|hello|hey|thanks|thank you|why|who are you|what is)\b",),
)
VERBS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "attack": (("砸", "打碎", "打破", "敲碎", "攻击", "揍", "踢", "杀", "放火", "点燃", "烧", "刺", "捅", "砍", "拍死"),
               (r"\bsmash", r"\bbreak\b", r"\bhit\b", r"\battack", r"\bkill", r"\bpunch", r"\bkick",
                r"\bstab", r"\bset (.+ )?on fire\b", r"\bset fire\b", r"\bburn\b", r"\bignite\b", r"\bswat\b",
                r"\bstrike\b")),
    "eat": (("吃", "吞", "咽", "舔", "嚼", "含在嘴"), (r"\beat\b", r"\bswallow", r"\blick", r"\bchew", r"\btaste\b")),
    "hide": (("躲", "藏起", "藏在", "藏到", "藏身"), (r"\bhide\b", r"\bduck (under|behind)\b", r"\bcrouch (under|behind)\b")),
    "light": (("照亮", "照一照", "照向", "打开手电", "开手电", "手电照", "照着"),
              (r"\bshine\b", r"\b(turn|switch) on (the |my )?(flashlight|torch)\b", r"\blight up\b")),
    # use verbs that clearly mean "operate", these beat take ("拿起电话打给保安")
    "use_strong": (("打给", "打电话", "拨打", "拨号", "刷卡", "刷", "插入", "插进", "插上", "戴上", "塞上", "塞进耳",
                    "播放", "换上", "装上", "合上", "泼", "喷", "割断", "割", "剪断", "打开样本盒", "打开盒"),
                   (r"\bcall\b", r"\bdial", r"\bswipe", r"\binsert", r"\bplug\b", r"\bput on\b", r"\bwear\b",
                    r"\bplay\b", r"\breplace\b", r"\binstall\b", r"\bfit\b", r"\bsplash", r"\bpour", r"\bspray",
                    r"\bcut\b", r"\bslice\b", r"\bflip the breaker\b")),
    "take": (("拿", "取", "捡", "抓", "带上", "拔下", "拔出", "收起"),
             (r"\btake\b", r"\bgrab", r"\bpick (it |them )?up\b", r"\bpick up\b", r"\bget\b", r"\bcatch\b",
              r"\bcollect\b", r"\bunplug\b")),
    "use_weak": (("用", "使用", "打开", "按", "启动", "开启", "操作"),
                 (r"\buse\b", r"\bopen\b", r"\bpress\b", r"\bpush\b", r"\bturn on\b", r"\bswitch on\b",
                  r"\boperate\b", r"\bactivate\b")),
    "look": (("看", "翻", "查看", "检查", "观察", "读", "阅读", "搜", "找", "瞧", "端详", "研究"),
             (r"\blook\b", r"\bread\b", r"\bexamine", r"\binspect", r"\bcheck\b", r"\bsearch", r"\bstudy\b",
              r"\bpeer\b", r"\bwatch\b", r"\bflip through\b", r"\bbrowse\b", r"\bview\b")),
    "move": (("去", "走到", "走进", "走向", "进入", "前往", "回到", "跑到", "跑去", "离开", "进去", "过去"),
             (r"\bgo\b", r"\bwalk", r"\bhead\b", r"\brun\b", r"\benter\b", r"\bmove\b", r"\breturn\b",
              r"\bleave\b", r"\bexit\b", r"\bgo back\b")),
    "listen": (("听", "倾听"), (r"\blisten", r"\bhear\b")),
    "smell": (("闻", "嗅"), (r"\bsmell", r"\bsniff")),
    "touch": (("摸", "碰", "触", "按住"), (r"\btouch", r"\bfeel\b", r"\bstroke\b", r"\bpoke\b")),
    "talk": (("说", "喊", "叫", "问", "对话", "呼救", "大喊"), (r"\btalk", r"\bsay\b", r"\bshout", r"\byell",
                                                         r"\bscream", r"\bask\b", r"\bwhisper", r"\bspeak")),
    "wait": (("等", "休息", "待着", "不动", "屏住呼吸"), (r"\bwait", r"\brest\b", r"\bstay\b", r"\bdo nothing\b",
                                                   r"\bhold (my )?breath\b")),
}
# category resolution order (first hit wins), with the take/use tie handled in _category()
ORDER = ("attack", "eat", "hide", "light", "use_strong", "take", "use_weak", "look", "move",
         "listen", "smell", "touch", "talk", "wait")

MONSTER_ALIASES = (("蜂群", "果蝇群", "怪物", "黑云", "那团东西", "苍蝇", "果蝇们", "它们"),
                   ("swarm", "monster", "flies", "the cloud", "the thing", "creature"))
SUICIDAL = (("自杀", "跳楼", "割腕", "喝乙醇", "喝酒精"), (r"\bkill myself\b", r"\bsuicide\b", r"\bdrink (the )?(ethanol|alcohol)\b"))
FIRE_WORDS = (("火", "点燃", "烧"), (r"\bfire\b", r"\bburn", r"\bignite", r"\blight(er)?\b"))


def _has(text: str, table: tuple[tuple[str, ...], tuple[str, ...]]) -> bool:
    zh, en = table
    return any(k in text for k in zh) or any(re.search(p, text) for p in en)


# ------------------------------------------------------------------ entity matching


@dataclass(frozen=True)
class Mention:
    pos: int
    ident: str


_INDEX_CACHE: dict[int, tuple[World, list[tuple[str, tuple[str, ...]]]]] = {}


def _alias_index(world: World) -> list[tuple[str, tuple[str, ...]]]:
    """(alias, ids) sorted longest first. An alias may point at several ids."""
    cached = _INDEX_CACHE.get(id(world))
    if cached is not None and cached[0] is world:
        return cached[1]
    table: dict[str, list[str]] = {}

    def add(alias: str, ident: str) -> None:
        a = alias.strip().lower()
        if a and ident not in table.setdefault(a, []):
            table[a].append(ident)

    for group in (world.scenes, world.fixtures, world.items):
        for ident, d in group.items():
            for lang in ("zh", "en"):
                add(d["name"][lang], ident)
                for a in (d.get("aliases") or {}).get(lang, []):
                    add(str(a), ident)
    for lang_aliases in MONSTER_ALIASES:
        for a in lang_aliases:
            add(a, TARGET_MONSTER)
    index = sorted(((a, tuple(ids)) for a, ids in table.items()), key=lambda x: -len(x[0]))
    _INDEX_CACHE[id(world)] = (world, index)
    return index


def find_mentions(text: str, state: GameState, world: World) -> list[Mention]:
    """Things the text names, in reading order. Longest alias wins; ambiguous
    aliases resolve to whatever is present in the scene or inventory."""
    present = set(target_options(state, world))
    buf = text.lower()
    found: list[Mention] = []
    for alias, ids in _alias_index(world):
        ascii_alias = alias.isascii()
        pattern = (r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])") if ascii_alias else re.escape(alias)
        for m in re.finditer(pattern, buf):
            choice = next((i for i in ids if i in present), ids[0])
            found.append(Mention(m.start(), choice))
            buf = buf[:m.start()] + "\x00" * (m.end() - m.start()) + buf[m.end():]
    found.sort(key=lambda m: m.pos)
    seen: set[str] = set()
    out = []
    for m in found:
        if m.ident not in seen:
            seen.add(m.ident)
            out.append(m)
    return out


# ------------------------------------------------------------------ the judge


def _category(text: str, mentions: list[Mention], state: GameState, world: World) -> Optional[str]:
    hits = {name for name in ORDER if _has(text, VERBS[name])}
    if "light" in hits and not any(m.ident == "flashlight" for m in mentions) and not any(
            k in text for k in VERBS["light"][0]):
        hits.discard("light")
    for name in ORDER:
        if name in hits:
            if name == "take" and not any(world.kind(m.ident) == "item" or m.ident == TARGET_MONSTER
                                          for m in mentions) and "use_weak" in hits:
                return "use"
            return "use" if name.startswith("use_") else name
    if any(world.kind(m.ident) == "scene" for m in mentions):
        return "move"  # a bare place name: "corridor", "去机房"
    return None


def _pick_target(category: str, mentions: list[Mention], state: GameState, world: World) -> str:
    kinds = {m.ident: world.kind(m.ident) for m in mentions}
    held = set(state.items)
    here = set(items_here(state, world))

    def first(pred) -> Optional[str]:
        return next((m.ident for m in mentions if pred(m.ident)), None)

    if category == "move":
        return first(lambda i: kinds[i] == "scene") or TARGET_NONE
    if category == "light":
        return "flashlight"
    if category == "attack":
        return (first(lambda i: i == TARGET_MONSTER) or first(lambda i: kinds[i] == "fixture")
                or first(lambda i: kinds[i] == "item" and i not in held) or first(lambda i: kinds[i] == "item")
                or TARGET_NONE)
    if category == "use":
        return (first(lambda i: kinds[i] == "item" and (i in held or i in here))
                or first(lambda i: kinds[i] == "fixture") or first(lambda i: i == TARGET_MONSTER)
                or first(lambda i: kinds[i] == "item") or TARGET_NONE)
    if category == "take":
        return (first(lambda i: kinds[i] == "item") or first(lambda i: i == TARGET_MONSTER)
                or first(lambda i: kinds[i] == "fixture") or TARGET_NONE)
    if category == "hide":
        return first(lambda i: kinds[i] == "fixture") or TARGET_NONE
    return (first(lambda i: kinds[i] == "item") or first(lambda i: kinds[i] == "fixture")
            or first(lambda i: i == TARGET_MONSTER) or first(lambda i: kinds[i] == "scene") or TARGET_NONE)


def _usable_in_place(world: World) -> set[str]:
    """Items a rule lets you use without carrying them (world.yaml `reachable`)."""
    return {i for r in world.rules for i in (r.get("when") or {}).get("reachable", [])}


def mock_judgement(state: GameState, world: World, text: str) -> JudgeResult:
    raw = text.strip()
    low = raw.lower()
    mentions = find_mentions(raw, state, world)
    options = target_options(state, world)

    def result(p: float, reason: str, category: str, target: str, danger: int) -> JudgeResult:
        return normalize(JudgeResult(feasible=p, reason=reason, category=category, target=target,
                                     danger=danger, source="mock"), options)

    if not raw:
        return result(0.0, "not_an_action", "other", TARGET_NONE, 0)
    if _has(low, IMPOSSIBLE):
        cat = "move" if any(k in low for k in ("飞", "fly", "teleport", "瞬移", "传送")) else "other"
        return result(0.02, "physically_impossible", cat, TARGET_NONE, 1)

    category = _category(low, mentions, state, world)
    if category is None:
        if _has(low, NOT_ACTION) or not mentions:
            return result(0.05, "not_an_action", "other", TARGET_NONE, 0)
        category = "look" if mentions else "other"

    target = _pick_target(category, mentions, state, world)
    held, here = set(state.items), set(items_here(state, world))
    fixtures_here = set(world.scenes[state.scene].get("fixtures", []))
    exits = world.scenes[state.scene].get("exits", [])
    danger = 0
    if state.monster_near and category in ("move", "attack", "take", "use"):
        danger = 1
    if _has(low, SUICIDAL):
        return result(0.1, "against_world_rules", category, target, 3)

    # ---- missing_item: an instrument or object named but not at hand
    named_items = [m.ident for m in mentions if world.kind(m.ident) == "item"]
    in_place = _usable_in_place(world)
    if category in ("use", "attack", "light"):
        for i in named_items:
            if i in held:
                continue
            if i in here:
                if category == "use" and i not in in_place:
                    return result(0.3, "missing_item", category, target, danger)  # lying here, not carried
                continue
            return result(0.05, "missing_item", category, target, max(danger, 1 if category == "attack" else 0))
        if category == "light" and "flashlight" not in held:
            return result(0.05, "missing_item", category, target, danger)

    # ---- no_such_target
    if category == "move":
        if target == TARGET_NONE:
            return result(0.15, "no_such_target", category, target, danger)
        if target == state.scene:
            return result(0.9, "feasible", category, target, 0)
        if target not in exits:
            return result(0.05, "no_such_target", category, TARGET_NONE, danger)
        if world.scenes[target].get("ending_scene"):
            if "keycard" in held and state.has_flag("power_on"):
                return result(0.9, "feasible", category, target, danger)
            return result(0.1, "against_world_rules", category, target, danger)
        return result(0.95, "feasible", category, target, danger)
    if category in ("take", "eat", "look", "smell", "touch"):
        for i in named_items:
            if i not in held and i not in here:
                return result(0.05, "no_such_target", category, TARGET_NONE, danger)
    other_place = [m.ident for m in mentions if world.kind(m.ident) == "fixture" and m.ident not in fixtures_here]
    if other_place and target == TARGET_NONE:
        return result(0.05, "no_such_target", category, TARGET_NONE, danger)
    if target == TARGET_MONSTER and not state.monster_near and category in ("attack", "take", "use"):
        return result(0.2, "no_such_target", category, target, danger)

    # ---- against_world_rules
    if world.kind(target) == "fixture":
        fx = world.fixtures[target]
        if category == "attack" and fx.get("breakable") is False:
            return result(0.08, "against_world_rules", category, target, max(danger, 1))
        if category in ("use", "talk") and fx.get("works") is False:
            return result(0.35, "against_world_rules", category, target, danger)
        if target in ("card_reader", "revolving_door") and category == "use":
            if "keycard" not in held:
                return result(0.05, "missing_item", category, target, danger)
            if not state.has_flag("power_on"):
                return result(0.3, "against_world_rules", category, target, danger)
    if target == "keycard" and category == "use" and not state.has_flag("power_on") and state.scene == "reception":
        return result(0.3, "against_world_rules", category, target, danger)

    # ---- feasible, with a judgement of risk
    if category == "eat":
        edible = world.items.get(target, {}).get("edible", False)
        return result(0.9 if edible else 0.5, "feasible", category, target, 0 if edible else 2)
    if category == "take" and target == "fuse" and "cryo_gloves" not in held:
        return result(0.7, "feasible", category, target, 2)  # bare hands in a −80 °C freezer
    if category == "attack":
        fire = _has(low, FIRE_WORDS)
        return result(0.75 if target == TARGET_MONSTER else 0.6, "feasible", category, target,
                      2 if (target == TARGET_MONSTER or fire) else max(danger, 1))
    p = {"look": 0.97, "hide": 0.9, "wait": 0.98, "listen": 0.97, "smell": 0.95, "talk": 0.95}.get(category, 0.92)
    return result(p, "feasible", category, target, danger)


class MockJudge(Judge):
    name = "mock"

    async def judge(self, state: GameState, world: World, text: str) -> JudgeResult:
        return mock_judgement(state, world, text)
