"""Unit tests for turn execution controller (app/engine/turn.py)."""

from __future__ import annotations

import asyncio
import pytest

from app.brain.groups import BrainGroups
from app.brain.lif import LIFSimulator
from app.content.loader import load_content
from app.engine.state import new_state
from app.engine.turn import execute_turn
from app.judge.mock import MockJudge


@pytest.fixture(scope="session")
def content():
    return load_content()


@pytest.fixture(scope="session")
def brain_groups():
    return BrainGroups()


@pytest.fixture(scope="session")
def simulator():
    return LIFSimulator()


@pytest.fixture
def judge():
    return MockJudge()


def test_system_command_costs_no_turn(content, judge, brain_groups, simulator):
    state = new_state(content.world, seed=42, lang="en")
    res = asyncio.run(execute_turn(state, "look", content.world, content, judge, brain_groups, simulator))

    assert res.is_system_command is True
    assert res.state.turn == 0
    assert len(res.output) > 0
    assert res.state.last_spikes == {}


def test_normal_action_advances_turn_and_runs_simulation(content, judge, brain_groups, simulator):
    state = new_state(content.world, seed=42, lang="en")
    res = asyncio.run(execute_turn(state, "open drawer and take flashlight", content.world, content, judge, brain_groups, simulator))

    assert res.is_system_command is False
    assert res.state.turn == 1
    assert "flashlight" in res.state.items
    assert len(res.state.last_spikes) > 0
    kinds = [o["kind"] for o in res.output]
    assert "action" in kinds
    assert "brainlog" in kinds


def test_turn_reproducibility(content, judge, brain_groups, simulator):
    # Same inputs must produce 100% identical outputs
    state1 = new_state(content.world, seed=12345, lang="en")
    state2 = new_state(content.world, seed=12345, lang="en")

    actions = ["look at the desk", "take flashlight", "go to the corridor"]

    for act in actions:
        res1 = asyncio.run(execute_turn(state1, act, content.world, content, judge, brain_groups, simulator))
        res2 = asyncio.run(execute_turn(state2, act, content.world, content, judge, brain_groups, simulator))

        assert res1.state.turn == res2.state.turn
        assert res1.state.scene == res2.state.scene
        assert res1.state.items == res2.state.items
        assert res1.state.sync == res2.state.sync
        assert res1.state.last_spikes == res2.state.last_spikes
        assert [o["text"] for o in res1.output] == [o["text"] for o in res2.output]


def test_sensory_feeding_fatigue(content, judge, brain_groups, simulator):
    state = new_state(content.world, seed=99, lang="en")
    # Feed tap repeatedly
    res = asyncio.run(execute_turn(state, "tap on the desk", content.world, content, judge, brain_groups, simulator))
    assert res.state.stim_fatigue.get("touch") == 1

    res = asyncio.run(execute_turn(state, "tap again", content.world, content, judge, brain_groups, simulator))
    assert res.state.stim_fatigue.get("touch") == 2


def test_server_terminal_qa(content, judge, brain_groups, simulator):
    state = new_state(content.world, seed=100, lang="en")
    state.scene = "server_room"
    state.set_flag("power_on")

    # 1. status
    res = asyncio.run(execute_turn(state, "status", content.world, content, judge, brain_groups, simulator))
    assert any("TERMINAL" in o["text"] for o in res.output)

    # 2. kill -9 specimen_F
    res = asyncio.run(execute_turn(state, "kill -9 specimen_F", content.world, content, judge, brain_groups, simulator))
    assert any("Permission denied" in o["text"] for o in res.output)

    # 3. stimulate PAM
    init_sync = state.sync
    res = asyncio.run(execute_turn(state, "stimulate PAM", content.world, content, judge, brain_groups, simulator))
    assert state.sync == init_sync + 15
    assert state.monster_block > 0


def test_neuro_hijack_triggers_at_high_sync(content, judge, brain_groups, simulator):
    state = new_state(content.world, seed=777, lang="en")
    state.sync = 85
    # Simulate high MN9 feeding spikes from previous turn
    state.last_spikes = {"monster.feed": 50, "monster.attack": 5, "monster.retreat": 2}

    # At 85% sync, hijack has high probability of triggering
    # Try a few seeds to verify hijack trigger
    triggered = False
    for seed_val in range(10):
        test_state = new_state(content.world, seed=seed_val, lang="en")
        test_state.sync = 85
        test_state.last_spikes = {"monster.feed": 50, "monster.attack": 5, "monster.retreat": 2}
        res = asyncio.run(execute_turn(test_state, "look around", content.world, content, judge, brain_groups, simulator))
        if any(o["kind"] == "hijack" for o in res.output):
            triggered = True
            break

    assert triggered, "Expected neuro-hijack to trigger across test seeds at sync=85"


# ------------------------------------------------------------------ playtest 11-16


def _run(content, judge, brain_groups, simulator, state, text):
    return asyncio.run(execute_turn(state, text, content.world, content, judge, brain_groups, simulator))


def test_one_character_input_costs_nothing(content, judge, brain_groups, simulator):
    state = new_state(content.world, seed=42, lang="zh")
    res = _run(content, judge, brain_groups, simulator, state, "把")
    assert res.is_system_command and res.state.turn == 0 and res.state.sync == 0
    assert res.output[0]["kind"] == "system"


def test_looking_shows_the_things_own_description(content, judge, brain_groups, simulator):
    state = new_state(content.world, seed=42, lang="en")
    res = _run(content, judge, brain_groups, simulator, state, "look at the drawer")
    texts = " ".join(o["text"] for o in res.output if o["kind"] == "action")
    assert "flashlight" in texts.lower() and "paper clips" in texts


def test_silence_line_is_not_every_turn(content, judge, brain_groups, simulator):
    state = new_state(content.world, seed=42, lang="en")
    silences = 0
    for text in ["look at the desk", "look at the drawer", "look at the phone",
                 "look at the door", "look at the card reader", "wait"]:
        res = _run(content, judge, brain_groups, simulator, state, text)
        state = res.state
        silences += sum(1 for o in res.output if o["kind"] == "silence")
    assert silences <= 2


def test_revisit_uses_short_scene_line(content, judge, brain_groups, simulator):
    state = new_state(content.world, seed=42, lang="en")
    for text in ["go to the corridor", "go to reception", "go to the corridor"]:
        res = _run(content, judge, brain_groups, simulator, state, text)
        state = res.state
    scene = [o["text"] for o in res.output if o["kind"] == "scene"]
    revisits = [v["en"] for v in content.world.descriptions["revisit"]["corridor"]]
    assert scene and scene[0] in revisits
