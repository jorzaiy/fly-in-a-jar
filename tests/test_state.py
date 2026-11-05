import json

import pytest

from app.engine.state import (
    MAX_STATE_BYTES, GameState, StateError, fit_size, new_state, parse_state,
)


def test_new_state_roundtrip(world, state):
    raw = state.to_json()
    again = parse_state(raw, world)
    assert again == state
    assert again.version == 2 and again.scene == "reception" and again.sync == 0


def test_design_example_state_parses(world):
    example = {
        "version": 2, "seed": 834201, "turn": 12, "lang": "en", "brainlog": True,
        "scene": "cold_storage", "items": ["flashlight", "lighter", "cryo_gloves"],
        "taken": ["flashlight", "lighter", "cryo_gloves"], "flags": ["light_on"], "sync": 43,
        "monster_near": True, "monster_block": 0, "monster_stunned": 0, "caught_fly": False,
        "last_spikes": {"GF": 3, "P9": 41, "MDN": 0, "MN9": 2, "LC": 18, "MBON": 7, "PAM": 9, "EPG": 22},
        "stim_fatigue": {"mechano": 1}, "clues_found": [1, 6],
        "used_fragments": ["m_approach_03", "an_vis_11"],
        "recent_actions": [{"text": "open freezer", "result": "ok"}], "ended": None,
    }
    s = parse_state(json.dumps(example), world)
    assert s.size_bytes() < MAX_STATE_BYTES


def test_size_cap_rejects_big_state(state):
    data = json.loads(state.to_json())
    data["used_fragments"] = [f"fragment_{i:05d}" for i in range(2000)]
    raw = json.dumps(data)
    assert len(raw.encode()) > MAX_STATE_BYTES
    with pytest.raises(StateError):
        parse_state(raw)
    with pytest.raises(StateError):
        parse_state(data)


def test_fit_size_trims_used_fragments(state):
    state.used_fragments = [f"fragment_{i:05d}" for i in range(2000)]
    assert state.size_bytes() > MAX_STATE_BYTES
    fit_size(state)
    assert state.size_bytes() <= MAX_STATE_BYTES
    assert state.used_fragments[-1] == "fragment_01999"  # newest kept


@pytest.mark.parametrize("patch", [
    {"version": 1}, {"sync": 101}, {"sync": -1}, {"lang": "fr"}, {"hacked": True},
    {"ended": "won"}, {"recent_actions": [{"text": "x", "result": "ok"}] * 6},
])
def test_invalid_states_rejected(state, patch):
    data = json.loads(state.to_json())
    data.update(patch)
    with pytest.raises(StateError):
        parse_state(data)


def test_unknown_ids_rejected(world, state):
    data = json.loads(state.to_json())
    data["scene"] = "moon"
    with pytest.raises(StateError):
        parse_state(data, world)
    data = json.loads(state.to_json())
    data["items"] = ["banana"]
    with pytest.raises(StateError):
        parse_state(data, world)


def test_not_json_rejected():
    with pytest.raises(StateError):
        parse_state("{not json")


def test_recent_actions_keep_last_five(state):
    for i in range(8):
        state.record_action(f"a{i}", "success")
    assert [a.text for a in state.recent_actions] == ["a3", "a4", "a5", "a6", "a7"]


def test_caught_fly_flag_maps_to_field(state):
    state.set_flag("caught_fly")
    assert state.caught_fly and state.has_flag("caught_fly")
    state.clear_flag("caught_fly")
    assert not state.caught_fly
