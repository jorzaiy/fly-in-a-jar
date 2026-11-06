import pytest

from app.engine.commands import parse_command, run_command


@pytest.mark.parametrize("text", ["help", "look", "status", "inventory", "notes", "lang zh",
                                  "brainlog off", "restart", "帮助", "背包", "  LOOK  "])
def test_system_commands_cost_nothing(content, state, text):
    res = run_command(state, text, content, new_seed=lambda: 7)
    assert res is not None and res.output
    assert res.state.turn == 0 and res.state.sync == 0
    assert all(o["kind"] == "system" for o in res.output)


@pytest.mark.parametrize("text", ["look at the logbook", "help me", "go to the corridor", "lang klingon now",
                                  "打开抽屉拿手电筒"])
def test_actions_are_not_commands(content, state, text):
    assert run_command(state, text, content) is None


def test_look_lists_scene(content, state):
    lines = [o["text"] for o in run_command(state, "look", content).output]
    assert lines[0] == "[Reception]"
    assert any("Corridor" in line and "exit (locked)" in line for line in lines)
    assert any("Flashlight" in line for line in lines)


def test_lang_switch_keeps_progress(content, state):
    state.items = ["flashlight"]
    res = run_command(state, "lang zh", content)
    assert res.state.lang == "zh" and res.output[0]["text"] == "已切换为中文。"
    res = run_command(res.state, "inventory", content)
    assert "手电筒" in res.output[0]["text"]
    assert run_command(state, "lang", content).output[0]["text"].startswith("用法")


def test_brainlog_toggle(content, state):
    assert run_command(state, "brainlog off", content).state.brainlog is False
    assert run_command(state, "brainlog on", content).state.brainlog is True


def test_notes_and_status(content, state):
    assert "not figured" in run_command(state, "notes", content).output[0]["text"]
    state.clues_found = [4]
    out = run_command(state, "notes", content).output
    assert out[1]["text"].startswith("#4 ")
    state.sync = 72
    state.set_flag("power_on")
    out = run_command(state, "status", content).output
    assert "72%" in out[0]["text"] and "instinct" in out[0]["text"] and "power on" in out[1]["text"]


def test_restart(content, state):
    state.sync, state.turn, state.scene, state.lang = 50, 9, "corridor", "zh"
    res = run_command(state, "restart", content, new_seed=lambda: 42)
    assert res.state.seed == 42 and res.state.sync == 0 and res.state.turn == 0
    assert res.state.scene == "reception" and res.state.lang == "zh"


def test_parse_command():
    assert parse_command("lang en") == ("lang", "en")
    assert parse_command("look around here") is None
