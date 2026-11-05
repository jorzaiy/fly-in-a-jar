"""Rules engine: every ending is reachable through plain rule calls."""

import pytest

from app.engine.rules import (
    add_sync, apply_action, classify, fail_sync, items_here, resolve_turn, tick_countdowns,
)


def act(state, world, category, target):
    return apply_action(state, world, category, target)


def go(state, world, *path):
    for scene in path:
        out = act(state, world, "move", scene)
        assert out.moved_to == scene, (state.scene, scene, out)


def take(state, world, item):
    out = act(state, world, "take", item)
    assert out.took == item and not out.blocked, out
    return out


def power_on(state, world):
    """reception -> gloves -> fuse -> power. Ends in the server room."""
    go(state, world, "corridor")
    take(state, world, "cryo_gloves")
    go(state, world, "cold_storage")
    take(state, world, "fuse")
    go(state, world, "corridor", "server_room")
    out = act(state, world, "use", "fuse_box")
    assert out.rule_id == "restore_power"
    assert state.has_flag("power_on") and "fuse" not in state.items


def get_keycard(state, world):
    """From anywhere reachable via corridor: scalpel then keycard. Ends in em_room."""
    go(state, world, "corridor", "prep_room")
    take(state, world, "scalpel")
    go(state, world, "em_room")
    take(state, world, "keycard")


# ------------------------------------------------------------------ endings


def test_ending_escaped(world, state):
    take(state, world, "flashlight")
    out = act(state, world, "look", "visitor_log")
    assert out.rule_id == "read_log" and out.clue == 4 and 4 in state.clues_found
    power_on(state, world)
    get_keycard(state, world)
    go(state, world, "prep_room", "corridor", "reception")
    out = act(state, world, "use", "keycard")
    assert out.rule_id == "escape" and out.ending == "escaped" and state.ended == "escaped"
    assert out.fragment == ("ending", "escaped")


def test_ending_escaped_by_moving_to_exit(world, state):
    power_on(state, world)
    get_keycard(state, world)
    go(state, world, "prep_room", "corridor", "reception")
    out = act(state, world, "move", "exit")
    assert state.ended == "escaped" and out.moved_to is None


def test_ending_consumed(world, state, cfg):
    while state.ended is None:
        out = resolve_turn(state, world, feasible=0.0, reason="physically_impossible",
                           category="move", target="none", danger=3, cfg=cfg)
        assert out.verdict == "fail"
    assert state.sync == 100 and state.ended == "consumed" and out.ending == "consumed"


def test_ending_absorbed(world, state):
    power_on(state, world)
    go(state, world, "corridor", "prep_room")
    take(state, world, "slide_4096")
    go(state, world, "em_room")
    out = act(state, world, "use", "slide_4096")
    assert out.rule_id == "view_slide" and out.clue == 12 and state.has_flag("saw_slide")
    # low sync: the microscope is only a microscope
    out = act(state, world, "use", "electron_microscope")
    assert out.rule_id != "absorbed" and state.ended is None
    add_sync(state, 70)
    out = act(state, world, "use", "electron_microscope")
    assert out.rule_id == "absorbed" and state.ended == "absorbed"


def _burn_server_route(state, world):
    take(state, world, "earplugs")
    out = act(state, world, "use", "earplugs")
    assert out.rule_id == "plug_ears" and state.has_flag("ears_plugged")
    power_on(state, world)
    take(state, world, "lighter")
    take(state, world, "usb_drive")
    out = act(state, world, "use", "usb_drive")
    assert out.rule_id == "read_usb" and out.clue == 11 and state.has_flag("read_usb")
    go(state, world, "corridor", "prep_room")
    take(state, world, "ethanol")
    go(state, world, "corridor", "server_room")
    out = act(state, world, "use", "server_rack")
    assert out.rule_id == "burn_server" and state.has_flag("server_burned")
    assert "ethanol" not in state.items
    assert state.monster_block == 3
    get_keycard(state, world)
    go(state, world, "prep_room", "corridor", "reception")


def test_ending_disconnected(world, state):
    _burn_server_route(state, world)
    out = act(state, world, "use", "card_reader")
    assert out.rule_id == "disconnected" and state.ended == "disconnected"


def test_caught_fly_turns_disconnected_into_escape(world, state):
    _burn_server_route(state, world)
    state.caught_fly = True
    out = act(state, world, "use", "keycard")
    assert out.rule_id == "escape" and state.ended == "escaped"


# ------------------------------------------------------------------ item rules


def test_fuse_frostbite_blocks_and_costs_sync(world, state):
    go(state, world, "corridor", "cold_storage")
    out = act(state, world, "take", "fuse")
    assert out.rule_id == "fuse_frostbite" and out.blocked
    assert "fuse" not in state.items and state.sync == 5
    assert out.fragment == ("item_use", "fuse_frostbite")


def test_keycard_tangled_without_scalpel(world, state):
    go(state, world, "corridor", "prep_room", "em_room")
    out = act(state, world, "take", "keycard")
    assert out.rule_id == "keycard_tangled" and out.blocked and "keycard" not in state.items


def test_keycard_without_power_does_not_escape(world, state):
    get_keycard(state, world)
    go(state, world, "prep_room", "corridor", "reception")
    out = act(state, world, "use", "keycard")
    assert state.ended is None and out.rule_id is None
    out = act(state, world, "move", "exit")
    assert out.blocked and out.reason == "against_world_rules" and state.scene == "reception"


def test_monster_tools(world, state):
    go(state, world, "corridor", "fly_room")
    for i in ("sugar_cube", "vial", "co2_pad"):
        take(state, world, i)
    out = act(state, world, "use", "vial")
    assert out.rule_id is None  # nothing to catch
    state.monster_near = True
    out = act(state, world, "use", "vial")
    assert out.rule_id == "catch_fly" and "vial_fly" in state.items and "vial" not in state.items
    assert state.caught_fly
    out = act(state, world, "use", "co2_pad")
    assert out.rule_id == "stun" and state.monster_stunned == 2 and "co2_pad" not in state.items
    out = act(state, world, "use", "sugar_cube")
    assert out.rule_id == "bait" and state.monster_block == 2
    tick_countdowns(state)
    assert (state.monster_block, state.monster_stunned) == (1, 1)
    tick_countdowns(state)
    tick_countdowns(state)
    assert (state.monster_block, state.monster_stunned) == (0, 0)


def test_lighter_and_firewall(world, state):
    state.items = ["lighter", "ethanol"]
    state.monster_near = True
    out = act(state, world, "attack", "monster")
    assert out.rule_id == "scare" and not state.monster_near
    out = act(state, world, "use", "ethanol")
    assert out.rule_id == "firewall" and state.monster_block == 4 and "ethanol" not in state.items


def test_light_and_recorder_and_box(world, state):
    take(state, world, "flashlight")
    out = act(state, world, "light", "flashlight")
    assert out.rule_id == "light" and state.has_flag("light_on") and out.dampen_anomaly == "visual"
    go(state, world, "corridor", "cold_storage")
    out = act(state, world, "use", "sample_box")
    assert out.rule_id == "open_box" and out.clue == 10 and state.sync == 5


def test_move_rules(world, state):
    out = act(state, world, "move", "server_room")
    assert out.blocked and out.reason == "no_such_target" and state.scene == "reception"
    out = act(state, world, "take", "scalpel")
    assert out.blocked and "scalpel" not in state.items
    assert "flashlight" in items_here(state, world)
    take(state, world, "flashlight")
    assert "flashlight" not in items_here(state, world)


# ------------------------------------------------------------------ verdicts and sync


@pytest.mark.parametrize("p,verdict", [(1.0, "success"), (0.65, "success"), (0.64, "partial"),
                                       (0.40, "partial"), (0.39, "fail"), (0.0, "fail")])
def test_classify(cfg, p, verdict):
    assert classify(p, cfg) == verdict


def test_resolve_turn_success_partial_fail(world, state, cfg):
    out = resolve_turn(state, world, feasible=0.95, reason="feasible", category="take",
                       target="flashlight", danger=0, cfg=cfg)
    assert out.verdict == "success" and "flashlight" in state.items and state.sync == 0 and state.turn == 1
    out = resolve_turn(state, world, feasible=0.5, reason="feasible", category="take",
                       target="earplugs", danger=2, cfg=cfg)
    assert out.verdict == "partial" and "earplugs" in state.items and out.sync_delta == 3
    out = resolve_turn(state, world, feasible=0.1, reason="missing_item", category="use",
                       target="card_reader", danger=2, cfg=cfg)
    assert out.verdict == "fail" and out.sync_delta == fail_sync(2, cfg) == 11
    assert out.fragment == ("verdict_fail", "missing_item")
    assert state.sync == 14 and state.turn == 3


def test_failed_take_changes_nothing_but_sync(world, state, cfg):
    resolve_turn(state, world, feasible=0.2, reason="against_world_rules", category="take",
                 target="flashlight", danger=0, cfg=cfg)
    assert state.items == [] and state.sync == 5


def test_sync_is_clamped(state):
    assert add_sync(state, 500) == 100 and state.sync == 100
    assert add_sync(state, -500) == -100 and state.sync == 0


def test_resolve_turn_refuses_after_ending(world, state, cfg):
    state.ended = "escaped"
    with pytest.raises(ValueError):
        resolve_turn(state, world, feasible=1, reason="feasible", category="wait", target="none",
                     danger=0, cfg=cfg)
