import shutil
from pathlib import Path

import pytest

from app.content.loader import (
    CONTENT_DIR, MVP_PER_CELL, ContentError, check_content, coverage, load_content, main, mvp_coverage, mvp_met,
    validate_ui, validate_world,
)
from app.content.schema import ENDINGS, HIJACK_KEYS


def test_shipped_content_is_valid(content):
    assert content.fragments
    assert validate_world(content.world) == []
    assert validate_ui(content.ui) == []


def test_every_key_has_a_fragment(content):
    rows = coverage(content.fragments, content.world)
    missing = [(r.category, r.key) for r in rows if r.have == 0]
    assert missing == []
    for e in ENDINGS:
        assert content.by_key("ending", e)
    for h in HIJACK_KEYS:
        assert content.by_key("hijack", h)


def test_every_rule_has_a_fragment(content):
    for rule in content.world.rules:
        cat, key = content.world.fragment_key_for_rule(rule)
        assert content.by_key(cat, key), f"no fragment for {cat}.{key}"


def test_world_counts(world):
    assert len(world.playable_scenes) == 7
    assert "exit" in world.scenes
    assert len(world.clues) == 13
    assert set(world.endings) == set(ENDINGS)
    for rid in ("burn_server", "absorbed", "disconnected", "escape"):
        world.rule(rid)


def test_cli_prints_coverage_and_passes(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "coverage" in out and "0 errors" in out
    assert "monster" in out and "i0 i1 i2 i3" in out


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    shutil.copy(CONTENT_DIR / "world.yaml", tmp_path / "world.yaml")
    shutil.copy(CONTENT_DIR / "ui.yaml", tmp_path / "ui.yaml")
    shutil.copytree(CONTENT_DIR / "fragments", tmp_path / "fragments")
    return tmp_path


def _write(scratch: Path, text: str) -> None:
    (scratch / "fragments" / "zz_bad.yaml").write_text(text, encoding="utf-8")


BAD_CASES = {
    "duplicate id": ("- id: monster_attack_01\n  category: monster\n  key: attack\n  intensity: 2\n"
                     "  zh: x\n  en: x\n", "monster_attack_01"),
    "missing en": ("- id: silence_default_09\n  category: silence\n  key: default\n  zh: 静\n",
                   "silence_default_09"),
    "unknown item": ("- id: silence_default_10\n  category: silence\n  key: default\n"
                     "  requires: {items: [banana]}\n  zh: 静\n  en: still\n", "silence_default_10"),
    "bad placeholder": ("- id: silence_default_11\n  category: silence\n  key: default\n"
                        "  zh: '{target} 静'\n  en: '{target} still'\n", "silence_default_11"),
    "tiers not allowed": ("- id: silence_default_12\n  category: silence\n  key: default\n"
                          "  tiers: {human: {zh: a, en: b}}\n", "silence_default_12"),
    "missing tier lang": ("- id: anomaly_visual_09\n  category: anomaly\n  key: visual\n  intensity: 0\n"
                          "  tiers: {human: {zh: a, en: b}, latent: {zh: c}}\n", "anomaly_visual_09"),
    "unknown key": ("- id: monster_dance_01\n  category: monster\n  key: dance\n  intensity: 1\n"
                    "  zh: a\n  en: b\n", "monster_dance_01"),
    "effects on item_use": ("- id: item_use_light_02\n  category: item_use\n  key: light\n"
                            "  effects: {sync: 2}\n  zh: a\n  en: b\n", "item_use_light_02"),
    "sync out of range": ("- id: monster_attack_09\n  category: monster\n  key: attack\n  intensity: 3\n"
                          "  effects: {sync: 40}\n  zh: a\n  en: b\n", "monster_attack_09"),
    "clue 13 without sync_min": ("- id: clue_13_02\n  category: clue\n  key: clue_13\n  zh: a\n  en: b\n",
                                 "clue_13_02"),
}


@pytest.mark.parametrize("case", sorted(BAD_CASES))
def test_validator_reports_bad_fragment_id(scratch, case):
    text, bad_id = BAD_CASES[case]
    _write(scratch, text)
    _, _, _, errors, _ = check_content(scratch)
    assert any(bad_id in e for e in errors), errors
    with pytest.raises(ContentError) as exc:
        load_content(scratch)
    assert bad_id in str(exc.value)


def test_missing_generic_is_an_error(scratch):
    (scratch / "fragments" / "drift.yaml").unlink()
    _, _, _, errors, _ = check_content(scratch)
    assert any("drift.generic" in e for e in errors)


def test_cli_exit_code_on_error(scratch, capsys):
    _write(scratch, BAD_CASES["missing en"][0])
    assert main([str(scratch)]) == 1
    assert "ERROR" in capsys.readouterr().out


def test_yaml_parse_error_is_reported(scratch):
    _write(scratch, "- id: [unclosed\n")
    _, _, _, errors, _ = check_content(scratch)
    assert any("zz_bad.yaml" in e and "YAML" in e for e in errors)


def test_ui_boolean_keys_are_caught():
    assert any("not a string" in e for e in validate_ui({"brainlog": {True: {"zh": "a", "en": "b"}}}))


# ------------------------------------------------------------- MVP coverage target


def test_mvp_cells_cover_every_category_and_intensity(content):
    cells = mvp_coverage(content.fragments, content.world)
    labels = [c.label for c in cells]
    assert len(labels) == len(set(labels))
    for cat in ("monster", "anomaly"):
        assert [f"{cat}@i{i}" for i in range(4)] == [l for l in labels if l.startswith(f"{cat}@")]
    assert "silence" in labels and "ending" in labels
    assert len(cells) == 11 + 2 * 4  # 11 single-cell categories + monster/anomaly x 4
    assert all(c.want == MVP_PER_CELL == 2 for c in cells)


def test_mvp_ignores_generic_fragments(content):
    silence = next(c for c in mvp_coverage(content.fragments, content.world) if c.label == "silence")
    assert silence.have == len(content.by_key("silence", "default"))


def _monster(n: int, intensity: int) -> str:
    return (f"- id: monster_approach_{n:02d}\n  category: monster\n  key: approach\n  intensity: {intensity}\n"
            f"  effects: {{monster_near: true}}\n  zh: 嗡\n  en: hum\n")


def test_mvp_cell_reaches_target_when_fragments_are_added(scratch):
    _, _, frags, _, _ = check_content(scratch)
    world = load_content(scratch).world
    before = {c.label: c.have for c in mvp_coverage(frags, world)}
    _write(scratch, _monster(90, 3) + _monster(91, 3))
    _, _, frags, errors, _ = check_content(scratch)
    assert errors == []
    after = {c.label: c for c in mvp_coverage(frags, world)}
    assert after["monster@i3"].have == before["monster@i3"] + 2
    assert after["monster@i3"].ok
    assert after["monster@i2"].have == before["monster@i2"]


def test_mvp_flag_fails_cli_until_target_met(scratch, capsys):
    _, _, frags, _, _ = check_content(scratch)
    world = load_content(scratch).world
    short = [c for c in mvp_coverage(frags, world) if not c.ok]
    assert main([str(scratch)]) == 0  # MVP is informational without --mvp
    out = capsys.readouterr().out
    assert "MVP cells" in out
    if short:
        assert main(["--mvp", str(scratch)]) == 1
        assert "MVP not met" in capsys.readouterr().out
        assert not mvp_met(frags, world)


def test_mvp_met_when_every_cell_has_two(scratch, capsys):
    # Pad every short cell with valid fragments, then --mvp passes.
    _, _, frags, _, _ = check_content(scratch)
    world = load_content(scratch).world
    keys = {"opening": "default", "verdict_partial": "default", "drift": "default", "silence": "default",
            "scene_enter": world.playable_scenes[0], "action": "look", "verdict_fail": "missing_item",
            "monster": "feed", "anomaly": "visual", "clue": "clue_9", "item_use": "light",
            "hijack": "eat", "ending": "escaped"}
    text, n = "", 0
    for c in mvp_coverage(frags, world):
        for _ in range(c.want - c.have if not c.ok else 0):
            n += 1
            extra = ""
            if c.intensity is not None:
                extra = f"  intensity: {c.intensity}\n"
                if c.intensity >= 2:
                    extra += "  effects: {sync: 2}\n"
            text += (f"- id: {c.category}_{keys[c.category]}_9{n:02d}\n  category: {c.category}\n"
                     f"  key: {keys[c.category]}\n{extra}  zh: 测\n  en: test\n")
    _write(scratch, text)
    _, _, frags, errors, _ = check_content(scratch)
    assert errors == []
    assert all(c.ok for c in mvp_coverage(frags, world))
    assert mvp_met(frags, world)
    assert main(["--mvp", "--quiet", str(scratch)]) == 0
    assert "MVP met" in capsys.readouterr().out
