"""Load and validate content/: world.yaml, ui.yaml and fragments/*.yaml (design §8).

`load_content()` is called at startup and refuses to return on any error
(requirements 5.3). `python -m content.validate` runs the same checks and
prints a coverage table.
"""

from __future__ import annotations

import re
import string
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from .schema import (
    ANOMALY_KEYS, CATEGORIES, ENDINGS, FAIL_REASONS, HIJACK_KEYS,
    MONSTER_KEYS, TARGET_MONSTER, TARGET_NONE, TIERS,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = REPO_ROOT / "content"
LANGS = ("zh", "en")


class ContentError(Exception):
    """Content failed validation. `.errors` lists every problem."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("content validation failed:\n  " + "\n  ".join(errors))


# --------------------------------------------------------------------- world


@dataclass
class World:
    raw: dict[str, Any]

    @property
    def start_scene(self) -> str:
        return self.raw["start_scene"]

    @property
    def scenes(self) -> dict[str, dict]:
        return self.raw["scenes"]

    @property
    def fixtures(self) -> dict[str, dict]:
        return self.raw["fixtures"]

    @property
    def items(self) -> dict[str, dict]:
        return self.raw["items"]

    @property
    def flags(self) -> list[str]:
        return self.raw["flags"]

    @property
    def clues(self) -> dict[int, dict]:
        return self.raw["clues"]

    @property
    def rules(self) -> list[dict]:
        return self.raw["rules"]

    @property
    def endings(self) -> dict[str, dict]:
        return self.raw["endings"]

    @property
    def judge_rules_en(self) -> list[str]:
        return self.raw.get("judge_rules_en", [])

    @property
    def playable_scenes(self) -> list[str]:
        return [s for s, d in self.scenes.items() if not d.get("ending_scene")]

    def rule(self, rule_id: str) -> dict:
        for r in self.rules:
            if r["id"] == rule_id:
                return r
        raise KeyError(rule_id)

    def kind(self, ident: str) -> str | None:
        """'scene' | 'fixture' | 'item' | 'monster' | 'none' | None."""
        if ident in self.scenes:
            return "scene"
        if ident in self.fixtures:
            return "fixture"
        if ident in self.items:
            return "item"
        if ident in (TARGET_MONSTER, TARGET_NONE):
            return ident
        return None

    def name(self, ident: str, lang: str) -> str:
        for table in (self.scenes, self.fixtures, self.items):
            if ident in table:
                return table[ident]["name"][lang]
        if ident == TARGET_MONSTER:
            return "蜂群" if lang == "zh" else "the swarm"
        return ident

    def fragment_key_for_rule(self, rule: dict) -> tuple[str, str]:
        """(category, key) of the fragment that narrates a rule (design §3)."""
        eff = rule.get("effects") or {}
        if "ending" in eff:
            return "ending", eff["ending"]
        if "clue" in eff:
            return "clue", f"clue_{eff['clue']}"
        return "item_use", rule["id"]

    def item_use_keys(self) -> list[str]:
        return [r["id"] for r in self.rules if self.fragment_key_for_rule(r)[0] == "item_use"]


def _names_ok(obj: Any, where: str, errors: list[str]) -> None:
    if not isinstance(obj, dict) or any(not isinstance(obj.get(l), str) or not obj.get(l).strip() for l in LANGS):
        errors.append(f"world: {where}: name needs non-empty zh and en")


def validate_world(world: World) -> list[str]:
    errs: list[str] = []
    w = world.raw
    for key in ("start_scene", "scenes", "fixtures", "items", "flags", "clues", "rules", "endings"):
        if key not in w:
            errs.append(f"world: missing top-level key '{key}'")
    if errs:
        return errs
    if w["start_scene"] not in world.scenes:
        errs.append(f"world: start_scene '{w['start_scene']}' is not a scene")

    for sid, s in world.scenes.items():
        _names_ok(s.get("name"), f"scene {sid}", errs)
        for ex in s.get("exits", []):
            if ex not in world.scenes:
                errs.append(f"world: scene {sid}: exit '{ex}' is not a scene")
            elif sid not in world.scenes[ex].get("exits", []) and not world.scenes[ex].get("ending_scene"):
                errs.append(f"world: scene {sid}: exit '{ex}' has no way back")
        for fx in s.get("fixtures", []):
            if fx not in world.fixtures:
                errs.append(f"world: scene {sid}: unknown fixture '{fx}'")
            elif world.fixtures[fx].get("scene") != sid:
                errs.append(f"world: fixture {fx} listed in {sid} but its scene is {world.fixtures[fx].get('scene')}")

    for fid, f in world.fixtures.items():
        _names_ok(f.get("name"), f"fixture {fid}", errs)
        if f.get("scene") not in world.scenes:
            errs.append(f"world: fixture {fid}: unknown scene '{f.get('scene')}'")
    ids = list(world.scenes) + list(world.fixtures) + list(world.items)
    dupes = {i for i in ids if ids.count(i) > 1}
    for d in sorted(dupes):
        errs.append(f"world: id '{d}' is used by more than one scene/fixture/item")

    for iid, it in world.items.items():
        _names_ok(it.get("name"), f"item {iid}", errs)
        loc = it.get("location")
        if loc is not None and loc not in world.scenes:
            errs.append(f"world: item {iid}: unknown location '{loc}'")
        c = it.get("container")
        if c is not None and (c not in world.fixtures or world.fixtures[c]["scene"] != loc):
            errs.append(f"world: item {iid}: container '{c}' is not a fixture in {loc}")

    for cid, c in world.clues.items():
        if not isinstance(cid, int):
            errs.append(f"world: clue id {cid!r} must be an integer")
        for lang in LANGS:
            if not c.get(lang):
                errs.append(f"world: clue {cid}: missing {lang}")
        for sc in c.get("scenes", []):
            if sc not in world.scenes:
                errs.append(f"world: clue {cid}: unknown scene '{sc}'")

    targets_ok = set(world.scenes) | set(world.fixtures) | set(world.items) | {TARGET_MONSTER, TARGET_NONE}
    seen: set[str] = set()
    for r in world.rules:
        rid = r.get("id", "?")
        if rid in seen:
            errs.append(f"world: rule id '{rid}' is duplicated")
        seen.add(rid)
        for t in r.get("trigger", []):
            for a in t.get("actions", []):
                if a not in CATEGORIES:
                    errs.append(f"world: rule {rid}: unknown action '{a}'")
            for tg in t.get("targets", []):
                if tg not in targets_ok:
                    errs.append(f"world: rule {rid}: unknown target '{tg}'")
        when = r.get("when") or {}
        for k, v in when.items():
            if k == "scene":
                if v not in world.scenes:
                    errs.append(f"world: rule {rid}: unknown scene '{v}'")
            elif k in ("items", "reachable", "not_items"):
                for i in v:
                    if i not in world.items:
                        errs.append(f"world: rule {rid}: unknown item '{i}'")
            elif k in ("flags", "not_flags"):
                for fl in v:
                    if fl not in world.flags:
                        errs.append(f"world: rule {rid}: unknown flag '{fl}'")
            elif k not in ("monster_near", "sync_min"):
                errs.append(f"world: rule {rid}: unknown condition '{k}'")
        eff = r.get("effects") or {}
        for k, v in eff.items():
            if k in ("set_flags", "clear_flags"):
                for fl in v:
                    if fl not in world.flags:
                        errs.append(f"world: rule {rid}: unknown flag '{fl}'")
            elif k == "consume":
                for i in v:
                    if i not in world.items:
                        errs.append(f"world: rule {rid}: unknown item '{i}'")
            elif k == "transform":
                for a, b in v.items():
                    if a not in world.items or b not in world.items:
                        errs.append(f"world: rule {rid}: bad transform {a}->{b}")
            elif k == "clue":
                if v not in world.clues:
                    errs.append(f"world: rule {rid}: unknown clue {v}")
            elif k == "ending":
                if v not in ENDINGS:
                    errs.append(f"world: rule {rid}: unknown ending '{v}'")
            elif k == "dampen_anomaly":
                if v not in ANOMALY_KEYS:
                    errs.append(f"world: rule {rid}: bad dampen_anomaly '{v}'")
            elif k not in ("block", "sync", "monster_block", "monster_stunned", "monster_near"):
                errs.append(f"world: rule {rid}: unknown effect '{k}'")

    for e in ENDINGS:
        if e not in world.endings:
            errs.append(f"world: ending '{e}' is not defined")
    for e, d in world.endings.items():
        if "rule" in d and d["rule"] not in seen:
            errs.append(f"world: ending {e}: unknown rule '{d['rule']}'")
    return errs


def load_world(path: Path | None = None) -> World:
    path = path or CONTENT_DIR / "world.yaml"
    with open(path, encoding="utf-8") as fh:
        return World(yaml.safe_load(fh))


# --------------------------------------------------------------------- ui


def load_ui(path: Path | None = None) -> dict:
    path = path or CONTENT_DIR / "ui.yaml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _ui_leaves(node: Any, path: str) -> Iterable[tuple[str, dict]]:
    """Yield every {zh, en} leaf of ui.yaml."""
    if isinstance(node, dict):
        if set(node) & set(LANGS):
            yield path, node
        else:
            for k, v in node.items():
                yield from _ui_leaves(v, f"{path}.{k}" if path else str(k))


def _non_string_keys(node: Any, path: str) -> Iterable[str]:
    """YAML 1.1 turns bare on/off/yes/no keys into booleans; catch that."""
    if isinstance(node, dict):
        for k, v in node.items():
            if not isinstance(k, str):
                yield f"ui: {path}: key {k!r} is not a string (quote it)"
            yield from _non_string_keys(v, f"{path}.{k}" if path else str(k))


def validate_ui(ui: dict) -> list[str]:
    errs = list(_non_string_keys(ui, ""))
    for path, leaf in _ui_leaves(ui, ""):
        for lang in LANGS:
            if not isinstance(leaf.get(lang), str) or not leaf[lang].strip():
                errs.append(f"ui: {path}: missing {lang}")
        fields = [{f for _, f, _, _ in string.Formatter().parse(leaf.get(l) or "") if f} for l in LANGS]
        if fields[0] != fields[1]:
            errs.append(f"ui: {path}: zh and en use different placeholders {fields[0]} vs {fields[1]}")
    return errs


def ui_text(ui: dict, key: str, lang: str, **kw: Any) -> str:
    node: Any = ui
    for part in key.split("."):
        node = node[part]
    text = node[lang]
    return text.format(**kw) if kw else text


# --------------------------------------------------------------------- fragments


@dataclass
class CategorySpec:
    keys: list[str]
    per_key: int
    by_intensity: bool = False
    tiers_allowed: bool = False
    target_ok: bool = False
    needs_generic: bool = True


def category_specs(world: World) -> dict[str, CategorySpec]:
    """Category table from fragment-guide.md."""
    return {
        "opening": CategorySpec(["default"], 3, tiers_allowed=True),
        "scene_enter": CategorySpec(world.playable_scenes, 3, tiers_allowed=True),
        "action": CategorySpec(list(CATEGORIES), 2, target_ok=True),
        "verdict_partial": CategorySpec(["default"], 6),
        "verdict_fail": CategorySpec(list(FAIL_REASONS), 4, target_ok=True),
        "monster": CategorySpec(list(MONSTER_KEYS), 2, by_intensity=True),
        "anomaly": CategorySpec(list(ANOMALY_KEYS), 2, by_intensity=True, tiers_allowed=True),
        "clue": CategorySpec([f"clue_{n}" for n in sorted(world.clues)], 1),
        "item_use": CategorySpec(world.item_use_keys(), 2),
        "hijack": CategorySpec(list(HIJACK_KEYS), 3, target_ok=True),
        "drift": CategorySpec(["default"], 4),
        "silence": CategorySpec(["default"], 8),
        "ending": CategorySpec(list(ENDINGS), 2, tiers_allowed=True, needs_generic=False),
    }


REQUIRES_KEYS = {"scene", "items", "flags", "not_flags", "monster_near", "sync_min", "sync_max"}
EFFECT_KEYS = {"sync", "give_item", "set_flag", "clear_flag", "monster_near"}
ID_RE = re.compile(r"^[a-z0-9_]+$")
PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")


@dataclass
class Issue:
    frag_id: str
    file: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.frag_id}: {self.message}"


@dataclass
class FragmentReport:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)


def load_fragments(directory: Path | None = None) -> tuple[list[dict], list[Issue]]:
    """Return (fragments, parse errors). Each fragment gets a `_file` key."""
    directory = directory or CONTENT_DIR / "fragments"
    frags: list[dict] = []
    errs: list[Issue] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            with open(path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            errs.append(Issue("-", path.name, f"YAML parse error: {exc}"))
            continue
        if data is None:
            continue
        if not isinstance(data, list):
            errs.append(Issue("-", path.name, "file must be a YAML list of fragments"))
            continue
        for i, frag in enumerate(data):
            if not isinstance(frag, dict):
                errs.append(Issue(f"#{i}", path.name, "fragment must be a mapping"))
                continue
            frag = dict(frag)
            frag["_file"] = path.name
            frags.append(frag)
    return frags, errs


def _texts(frag: dict) -> list[tuple[str, str, str]]:
    """(tier, lang, text) for every text in a fragment."""
    out = []
    if "tiers" in frag and isinstance(frag["tiers"], dict):
        for tier, body in frag["tiers"].items():
            if isinstance(body, dict):
                for lang in LANGS:
                    if isinstance(body.get(lang), str):
                        out.append((tier, lang, body[lang]))
    for lang in LANGS:
        if isinstance(frag.get(lang), str):
            out.append(("human", lang, frag[lang]))
    return out


def validate_fragments(frags: list[dict], world: World) -> FragmentReport:
    rep = FragmentReport()
    specs = category_specs(world)
    seen: dict[str, str] = {}

    def err(f: dict, msg: str) -> None:
        rep.errors.append(Issue(str(f.get("id", "?")), f.get("_file", "?"), msg))

    def warn(f: dict, msg: str) -> None:
        rep.warnings.append(Issue(str(f.get("id", "?")), f.get("_file", "?"), msg))

    for f in frags:
        fid, cat, key = f.get("id"), f.get("category"), f.get("key")
        for req in ("id", "category", "key"):
            if not f.get(req):
                err(f, f"missing required field '{req}'")
        if not fid or not cat or not key:
            continue
        if not isinstance(fid, str) or not ID_RE.match(fid):
            err(f, "id must be lowercase letters, digits and underscores")
        elif fid in seen:
            err(f, f"duplicate id (also in {seen[fid]})")
        else:
            seen[fid] = f["_file"]
        if not str(fid).startswith(f"{cat}_"):
            warn(f, f"id should start with '{cat}_' (<category>_<key>_<nn>)")

        spec = specs.get(cat)
        if spec is None:
            err(f, f"unknown category '{cat}'")
            continue
        if key != "generic" and key not in spec.keys:
            err(f, f"unknown key '{key}' for category '{cat}'")

        # intensity
        if "intensity" in f:
            if not isinstance(f["intensity"], int) or not 0 <= f["intensity"] <= 3:
                err(f, "intensity must be an integer 0–3")
            elif not spec.by_intensity:
                warn(f, f"intensity is ignored for category '{cat}'")
        elif spec.by_intensity and key != "generic":
            err(f, f"category '{cat}' needs intensity 0–3")

        # texts and tiers
        has_flat = any(l in f for l in LANGS)
        if "tiers" in f:
            if not spec.tiers_allowed:
                err(f, f"tiers are only allowed for opening, scene_enter, anomaly, ending (not '{cat}')")
            tiers = f["tiers"]
            if not isinstance(tiers, dict) or "human" not in tiers:
                err(f, "tiers must be a mapping with at least 'human'")
            else:
                for t, body in tiers.items():
                    if t not in TIERS:
                        err(f, f"unknown tier '{t}' (use {', '.join(TIERS)})")
                        continue
                    for lang in LANGS:
                        if not isinstance(body, dict) or not str(body.get(lang) or "").strip():
                            err(f, f"tier '{t}' is missing {lang}")
            if has_flat:
                err(f, "use either zh/en or tiers, not both")
        else:
            for lang in LANGS:
                if not str(f.get(lang) or "").strip():
                    err(f, f"missing {lang} text")

        for tier, lang, text in _texts(f):
            for ph in PLACEHOLDER_RE.findall(text):
                if ph != "target":
                    err(f, f"unknown placeholder '{{{ph}}}' (only {{target}} exists)")
                elif not spec.target_ok:
                    err(f, f"{{target}} is only allowed in action, verdict_fail, hijack (not '{cat}')")
            if cat != "ending":
                if lang == "zh" and len(text.strip()) > 100:
                    warn(f, f"zh text over 100 characters ({tier})")
                if lang == "en" and len(text.split()) > 60:
                    warn(f, f"en text over 60 words ({tier})")

        # requires
        req = f.get("requires") or {}
        if not isinstance(req, dict):
            err(f, "requires must be a mapping")
            req = {}
        for k, v in req.items():
            if k not in REQUIRES_KEYS:
                err(f, f"unknown requires key '{k}'")
            elif k == "scene":
                for s in (v if isinstance(v, list) else [v]):
                    if s not in world.scenes:
                        err(f, f"requires.scene: unknown scene '{s}'")
            elif k == "items":
                for i in (v if isinstance(v, list) else [v]):
                    if i not in world.items:
                        err(f, f"requires.items: unknown item '{i}'")
            elif k in ("flags", "not_flags"):
                for fl in (v if isinstance(v, list) else [v]):
                    if fl not in world.flags:
                        err(f, f"requires.{k}: unknown flag '{fl}'")
            elif k == "monster_near" and not isinstance(v, bool):
                err(f, "requires.monster_near must be true or false")
            elif k in ("sync_min", "sync_max") and (not isinstance(v, int) or not 0 <= v <= 100):
                err(f, f"requires.{k} must be an integer 0–100")

        # effects
        eff = f.get("effects") or {}
        if not isinstance(eff, dict):
            err(f, "effects must be a mapping")
            eff = {}
        if eff and cat == "item_use":
            err(f, "item_use fragments must not have effects (the rule engine applies them)")
        for k, v in eff.items():
            if k not in EFFECT_KEYS:
                err(f, f"unknown effects key '{k}'")
            elif k == "sync" and (not isinstance(v, int) or not -5 <= v <= 12):
                err(f, "effects.sync must be an integer from -5 to +12")
            elif k == "give_item" and v not in world.items:
                err(f, f"effects.give_item: unknown item '{v}'")
            elif k in ("set_flag", "clear_flag") and v not in world.flags:
                err(f, f"effects.{k}: unknown flag '{v}'")
            elif k == "monster_near" and not isinstance(v, bool):
                err(f, "effects.monster_near must be true or false")

        # guide conventions: warnings, they do not block startup
        if cat == "monster" and key == "attack" and not (eff.get("sync", 0) > 0):
            warn(f, "monster.attack should raise sync")
        if cat == "monster" and key == "approach" and eff.get("monster_near") is not True:
            warn(f, "monster.approach should set monster_near: true")
        if cat == "monster" and key == "retreat" and eff.get("monster_near") is not False:
            warn(f, "monster.retreat should set monster_near: false")
        if cat == "anomaly" and f.get("intensity", 0) >= 2 and not (eff.get("sync", 0) > 0):
            warn(f, "anomaly with intensity 2–3 should raise sync")
        if cat == "clue" and key == "clue_1" and eff.get("give_item") != "notebook_page":
            warn(f, "clue_1 should give_item: notebook_page")
        if cat == "clue" and key == "clue_13" and (req.get("sync_min") or 0) < 70:
            err(f, "clue_13 must have requires: {sync_min: 70}")

    # every category needs a generic fallback (requirements 5.4)
    for cat, spec in specs.items():
        if spec.needs_generic and not any(f.get("category") == cat and f.get("key") == "generic" for f in frags):
            rep.errors.append(Issue(f"{cat}.generic", "-", "missing generic fallback fragment"))
    return rep


@dataclass
class CoverageRow:
    category: str
    key: str
    want: int
    have: int
    by_intensity: dict[int, int] | None = None

    @property
    def status(self) -> str:
        if self.have == 0:
            return "MISSING"
        if self.by_intensity is not None:
            if any(self.by_intensity.get(i, 0) == 0 for i in range(4)):
                return "gaps"
            return "ok" if self.have >= self.want else "low"
        return "ok" if self.have >= self.want else "low"


def coverage(frags: list[dict], world: World) -> list[CoverageRow]:
    rows = []
    for cat, spec in category_specs(world).items():
        keys = list(spec.keys) + (["generic"] if spec.needs_generic else [])
        for key in keys:
            mine = [f for f in frags if f.get("category") == cat and f.get("key") == key]
            want = 1 if key == "generic" else spec.per_key * (4 if spec.by_intensity else 1)
            by_i = None
            if spec.by_intensity and key != "generic":
                by_i = {i: sum(1 for f in mine if f.get("intensity") == i) for i in range(4)}
            rows.append(CoverageRow(cat, key, want, len(mine), by_i))
    return rows


def format_coverage(rows: list[CoverageRow]) -> str:
    lines = [f"{'category':<16} {'key':<24} {'have':>4}/{'want':<4} {'i0 i1 i2 i3':<12} status", "-" * 70]
    for r in rows:
        bi = " ".join(f"{r.by_intensity[i]:>2}" for i in range(4)) if r.by_intensity else ""
        lines.append(f"{r.category:<16} {r.key:<24} {r.have:>4}/{r.want:<4} {bi:<12} {r.status}")
    total_have = sum(min(r.have, r.want) for r in rows)
    total_want = sum(r.want for r in rows)
    lines.append("-" * 70)
    lines.append(f"coverage {total_have}/{total_want} ({100 * total_have // max(total_want, 1)}%), "
                 f"{sum(1 for r in rows if r.have == 0)} keys with no fragment")
    return "\n".join(lines)


# MVP target (fragment-guide.md "MVP 覆盖目标"): at least this many non-generic
# fragments in every category x intensity cell. monster and anomaly have four
# cells (intensity 0-3); every other category is a single cell. The full
# per-key counts in category_specs() stay the stretch goal.
MVP_PER_CELL = 2


@dataclass
class MvpCell:
    category: str
    intensity: int | None  # None: category is not split by intensity
    have: int
    want: int = MVP_PER_CELL

    @property
    def ok(self) -> bool:
        return self.have >= self.want

    @property
    def label(self) -> str:
        return self.category if self.intensity is None else f"{self.category}@i{self.intensity}"


def mvp_coverage(frags: list[dict], world: World) -> list[MvpCell]:
    """One cell per category x intensity tier, counting non-generic fragments."""
    cells = []
    for cat, spec in category_specs(world).items():
        mine = [f for f in frags if f.get("category") == cat and f.get("key") in spec.keys]
        if spec.by_intensity:
            for i in range(4):
                cells.append(MvpCell(cat, i, sum(1 for f in mine if f.get("intensity") == i)))
        else:
            cells.append(MvpCell(cat, None, len(mine)))
    return cells


def mvp_met(frags: list[dict], world: World) -> bool:
    """MVP = every cell has MVP_PER_CELL fragments and every key has at least one."""
    return (all(c.ok for c in mvp_coverage(frags, world))
            and all(r.have > 0 for r in coverage(frags, world)))


def format_mvp(cells: list[MvpCell], table: bool = True) -> str:
    lines = []
    if table:
        lines.append(f"MVP target: >= {MVP_PER_CELL} non-generic fragments per category x intensity "
                     "('!' = below target)")
        lines.append(f"{'category':<16} {'i0':>4} {'i1':>4} {'i2':>4} {'i3':>4}   all")
        lines.append("-" * 44)
        by_cat: dict[str, list[MvpCell]] = {}
        for c in cells:
            by_cat.setdefault(c.category, []).append(c)
        for cat, cs in by_cat.items():
            def cell(c: MvpCell) -> str:
                return f"{c.have}{'' if c.ok else '!'}"
            if cs[0].intensity is None:
                lines.append(f"{cat:<16} {'':>4} {'':>4} {'':>4} {'':>4}   {cell(cs[0]):>3}")
            else:
                lines.append(f"{cat:<16} " + " ".join(f"{cell(c):>4}" for c in cs))
        lines.append("-" * 44)
    short = [c for c in cells if not c.ok]
    summary = f"MVP cells {len(cells) - len(short)}/{len(cells)} meet >= {MVP_PER_CELL}"
    if short:
        summary += "; below: " + ", ".join(f"{c.label} ({c.have})" for c in short)
    lines.append(summary)
    return "\n".join(lines)


# --------------------------------------------------------------------- all together


@dataclass
class Content:
    world: World
    ui: dict
    fragments: list[dict]
    warnings: list[Issue] = field(default_factory=list)

    def by_key(self, category: str, key: str) -> list[dict]:
        return [f for f in self.fragments if f["category"] == category and f["key"] == key]

    def text(self, key: str, lang: str, **kw: Any) -> str:
        return ui_text(self.ui, key, lang, **kw)


def check_content(content_dir: Path | None = None) -> tuple[World | None, dict | None, list[dict], list[str], list[Issue]]:
    """Run every check. Returns (world, ui, fragments, errors, warnings)."""
    content_dir = content_dir or CONTENT_DIR
    errors: list[str] = []
    try:
        world = load_world(content_dir / "world.yaml")
        errors += validate_world(world)
    except (OSError, yaml.YAMLError, AttributeError, TypeError) as exc:
        return None, None, [], [f"world.yaml: cannot load: {exc}"], []
    try:
        ui = load_ui(content_dir / "ui.yaml")
        errors += validate_ui(ui)
    except (OSError, yaml.YAMLError) as exc:
        ui = None
        errors.append(f"ui.yaml: cannot load: {exc}")
    frags, parse_errs = load_fragments(content_dir / "fragments")
    errors += [str(e) for e in parse_errs]
    rep = validate_fragments(frags, world)
    errors += [str(e) for e in rep.errors]
    return world, ui, frags, errors, rep.warnings


def load_content(content_dir: Path | None = None) -> Content:
    """Load everything or raise ContentError listing every bad ID."""
    world, ui, frags, errors, warnings = check_content(content_dir)
    if errors:
        raise ContentError(errors)
    assert world is not None and ui is not None
    return Content(world, ui, frags, warnings)


def main(argv: list[str] | None = None) -> int:
    """CLI for `python -m content.validate [--strict] [--mvp] [--quiet] [content_dir]`.

    --strict  warnings fail too
    --mvp     also fail when the MVP coverage target is not met
    --quiet   skip the coverage tables (the MVP summary line is still printed)
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    strict = "--strict" in argv
    mvp = "--mvp" in argv
    quiet = "--quiet" in argv
    rest = [a for a in argv if not a.startswith("--")]
    content_dir = Path(rest[0]) if rest else CONTENT_DIR
    world, _ui, frags, errors, warnings = check_content(content_dir)
    if world is not None and not quiet:
        print(format_coverage(coverage(frags, world)))
        print()
    if world is not None:
        print(format_mvp(mvp_coverage(frags, world), table=not quiet))
        if not quiet:
            print()
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    n_err = len(errors) + (len(warnings) if strict else 0)
    mvp_fail = mvp and (world is None or not mvp_met(frags, world))
    print(f"{len(frags)} fragments, {len(errors)} errors, {len(warnings)} warnings"
          + (" (strict)" if strict else "")
          + ((", MVP not met" if mvp_fail else ", MVP met") if mvp else ""))
    return 1 if n_err or mvp_fail else 0
