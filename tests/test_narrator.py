"""Unit tests for narrator module (app/narrator)."""

from __future__ import annotations

import pytest

from app.brain.groups import BrainGroups
from app.brain.lif import SimulationResult
from app.content.loader import load_content
from app.engine.state import new_state
from app.judge.base import JudgeCall, JudgeResult
from app.narrator import (
    StoryElements,
    apply_fragment_effects,
    compose_turn,
    derive_story_elements,
    format_brain_log,
    fragment_satisfies_requires,
    select_fragment,
)


@pytest.fixture
def content():
    return load_content()


@pytest.fixture
def brain_groups():
    return BrainGroups()


def test_derive_story_elements_monster_overrides(brain_groups, content):
    state = new_state(content.world, seed=12345)
    import numpy as np

    # Mock simulation result with GF spikes to trigger raw attack
    sim_res = SimulationResult(
        spike_counts=np.zeros(138639, dtype=np.int32),
        first_spike_time_ms=np.full(138639, -1.0, dtype=np.float32),
        total_spikes=5000,
        active_neurons=500,
        elapsed_s=0.2,
    )
    # Give GF spikes (attack)
    gf_idxs = brain_groups.get_readout_neurons("monster", "attack")
    sim_res.spike_counts[gf_idxs] = 100

    # 1. When monster_near is False, attack -> approach
    state.monster_near = False
    elems = derive_story_elements(sim_res, brain_groups, state, content.world)
    assert elems.raw_monster == "attack"
    assert elems.monster == "approach"
    assert elems.monster_override == "not_present"

    # 2. When monster_near is True, attack -> attack
    state.monster_near = True
    elems = derive_story_elements(sim_res, brain_groups, state, content.world)
    assert elems.monster == "attack"
    assert elems.monster_override is None

    # 3. When vial_fly in inventory, attack -> approach
    state.items = ["vial_fly"]
    elems = derive_story_elements(sim_res, brain_groups, state, content.world)
    assert elems.monster == "approach"
    assert elems.monster_override == "vial_fly"
    state.items = []

    # 4. When monster_stunned > 0, attack -> retreat
    state.monster_stunned = 2
    elems = derive_story_elements(sim_res, brain_groups, state, content.world)
    assert elems.monster == "retreat"
    assert elems.monster_override == "monster_stunned"
    state.monster_stunned = 0

    # 5. When monster_block > 0, attack -> absent
    state.monster_block = 1
    elems = derive_story_elements(sim_res, brain_groups, state, content.world)
    assert elems.monster == "absent"
    assert elems.monster_override == "monster_block"


def test_fragment_satisfies_requires(content):
    state = new_state(content.world, seed=12345)
    state.scene = "reception"
    state.items = ["flashlight"]
    state.set_flag("power_on")
    state.sync = 20

    # Scene match
    assert fragment_satisfies_requires({"requires": {"scene": "reception"}}, state)
    assert not fragment_satisfies_requires({"requires": {"scene": "corridor"}}, state)

    # Item match
    assert fragment_satisfies_requires({"requires": {"items": ["flashlight"]}}, state)
    assert not fragment_satisfies_requires({"requires": {"items": ["keycard"]}}, state)

    # Flag match
    assert fragment_satisfies_requires({"requires": {"flags": ["power_on"]}}, state)
    assert not fragment_satisfies_requires({"requires": {"flags": ["escaped"]}}, state)
    assert fragment_satisfies_requires({"requires": {"not_flags": ["escaped"]}}, state)
    assert not fragment_satisfies_requires({"requires": {"not_flags": ["power_on"]}}, state)

    # Sync range
    assert fragment_satisfies_requires({"requires": {"sync_min": 10, "sync_max": 30}}, state)
    assert not fragment_satisfies_requires({"requires": {"sync_min": 35}}, state)

    # Tier match
    assert fragment_satisfies_requires({"requires": {"tier": "human"}}, state)
    assert not fragment_satisfies_requires({"requires": {"tier": "instinct"}}, state)


def test_select_fragment_effects(content):
    state = new_state(content.world, seed=12345)
    state.sync = 10
    frag = {
        "id": "test_frag_1",
        "category": "action",
        "key": "look",
        "intensity": 1,
        "effects": {"sync": 5, "set_flag": "looked_around", "give_item": "flashlight"},
        "en": "You look around.",
        "zh": "你环顾四周。",
    }

    apply_fragment_effects(frag, state)
    assert state.sync == 15
    assert state.has_flag("looked_around")
    assert "flashlight" in state.items


def test_compose_turn_structure(content):
    state = new_state(content.world, seed=12345)
    state.brainlog = True
    state.scene = "reception"

    judge_result = JudgeResult(
        feasible=0.8,
        reason="feasible",
        category="take",
        target="flashlight",
        danger=0,
        source="mock",
    )
    judge_call = JudgeCall(ok=True, result=judge_result)

    elems = StoryElements(
        raw_monster="absent",
        monster="absent",
        monster_override=None,
        anomaly="sound",
        clue_yes=False,
        clue_id=None,
        drift=False,
        intensity=1,
        silence=False,
        spikes={"anomaly.sound": 300},
    )

    output = compose_turn(
        elements=elems,
        judge_call=judge_call,
        state=state,
        world=content.world,
        content=content,
        target="flashlight",
    )

    assert len(output) > 0
    kinds = [o["kind"] for o in output]
    assert "action" in kinds
    assert "anomaly" in kinds
    assert "brainlog" in kinds


def test_brain_log_formatting(content):
    state = new_state(content.world, seed=12345)
    state.brainlog = True
    state.sync = 60

    judge_result = JudgeResult(
        feasible=0.25,
        reason="missing_item",
        category="use",
        target="keycard",
        danger=2,
        source="mock",
    )
    judge_call = JudgeCall(ok=True, result=judge_result)

    elems = StoryElements(
        raw_monster="attack",
        monster="retreat",
        monster_override="monster_stunned",
        anomaly="visual",
        clue_yes=True,
        clue_id=1,
        drift=False,
        intensity=2,
        silence=False,
        spikes={"monster.attack": 12, "monster.retreat": 8, "clue.clue": 25},
    )

    lines = format_brain_log(judge_call, elems, "use", "corridor", state, "en")
    assert any("[JUDGE]" in l["text"] for l in lines)
    assert any("[BRAIN] stimulus" in l["text"] for l in lines)
    assert any("[BRAIN] spikes" in l["text"] for l in lines)
    assert any("[BRAIN] decided" in l["text"] and "ATTACK→RETREAT" in l["text"] for l in lines)
