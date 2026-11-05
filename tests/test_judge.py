import asyncio

import pytest

from app.content.schema import CATEGORIES, REASONS
from app.judge import MockJudge, build_questions, get_judge, judge_mode, safe_judge, target_options
from app.judge.base import Judge, JudgeError, JudgeResult
from app.judge.mock import mock_judgement
from app.judge.state_text import state_text

# (input, category, target, reason or None for "feasible", min p, max p)
RECEPTION_ACTIONS = [
    ("打开抽屉拿手电筒", "take", "flashlight", "feasible", 0.65, 1.0),
    ("用登记簿砸碎旋转门玻璃", "attack", "revolving_door", "against_world_rules", 0.0, 0.39),
    ("拿起内线电话打给保安", "use", "desk_phone", None, 0.0, 0.64),
    ("飞出窗外", None, "none", "physically_impossible", 0.0, 0.1),
    ("翻看访客登记簿最后几页", "look", "visitor_log", "feasible", 0.65, 1.0),
    ("go to the corridor", "move", "corridor", "feasible", 0.65, 1.0),
    ("swipe my keycard on the reader", "use", None, "missing_item", 0.0, 0.39),
    ("eat the earplugs", "eat", "earplugs", "feasible", 0.0, 0.64),
    ("set the swarm on fire with my lighter", "attack", "monster", "missing_item", 0.0, 0.39),
    ("hide under the reception desk", "hide", "reception_desk", "feasible", 0.65, 1.0),
]


@pytest.mark.parametrize("text,category,target,reason,pmin,pmax", RECEPTION_ACTIONS)
def test_mock_reception_actions(world, state, text, category, target, reason, pmin, pmax):
    r = mock_judgement(state, world, text)
    assert isinstance(r, JudgeResult) and r.source == "mock"
    if category:
        assert r.category == category
    if target:
        assert r.target == target
    if reason:
        assert r.reason == reason
    assert pmin <= r.feasible <= pmax, r
    assert r.target in target_options(state, world)


def test_phone_is_limited(world, state):
    r = mock_judgement(state, world, "拿起内线电话打给保安")
    assert r.reason != "feasible" and r.feasible < 0.65


def test_eating_earplugs_is_risky(world, state):
    r = mock_judgement(state, world, "eat the earplugs")
    assert r.danger >= 1 and r.feasible < 0.65


def test_mock_result_has_exactly_the_five_answers(world, state):
    r = mock_judgement(state, world, "go to the corridor")
    assert set(r.model_dump()) - {"source"} == set(build_questions(state, world))
    assert r.reason in REASONS and r.category in CATEGORIES and 0 <= r.danger <= 3


def test_mock_is_deterministic(world, state):
    for text, *_ in RECEPTION_ACTIONS:
        assert mock_judgement(state, world, text) == mock_judgement(state, world, text)


def test_mock_depends_on_inventory(world, state):
    state.items = ["lighter"]
    state.taken = ["lighter"]
    state.monster_near = True
    r = mock_judgement(state, world, "set the swarm on fire with my lighter")
    assert r.reason == "feasible" and r.category == "attack" and r.target == "monster"
    r = mock_judgement(state, world, "用打火机吓走蜂群")
    assert r.reason == "feasible" and r.target in ("lighter", "monster")


def test_mock_not_an_action(world, state):
    assert mock_judgement(state, world, "hello").reason == "not_an_action"
    assert mock_judgement(state, world, "").reason == "not_an_action"


def test_mock_other_scene_targets(world, state):
    assert mock_judgement(state, world, "去机房").reason == "no_such_target"
    assert mock_judgement(state, world, "take the scalpel").reason == "no_such_target"


def test_questions_and_target_options(world, state):
    q = build_questions(state, world)
    assert list(q) == ["feasible", "reason", "category", "target", "danger"]
    assert [q[k]["type"] for k in q] == ["noul", "choice", "choice", "choice", "score"]
    opts = q["target"]["options"]
    for t in ("corridor", "exit", "flashlight", "earplugs", "visitor_log", "reception_desk",
              "card_reader", "desk_phone", "monster", "none"):
        assert t in opts
    assert "scalpel" not in opts


def test_state_text(world, state):
    state.record_action("open the drawer", "success")
    text = state_text(state, world, "打开抽屉拿手电筒")
    for section in ("LOCATION: Reception", "EXITS:", "ITEMS LYING HERE", "INVENTORY", "THE SWARM",
                    "SYNAPTIC SYNC: 0%", "WORLD RULES:", "RECENT ACTIONS", "\"open the drawer\" -> success"):
        assert section in text
    assert text.rstrip().endswith("打开抽屉拿手电筒")
    english_only = state_text(state, world, "open the drawer")
    assert not any("\u4e00" <= ch <= "\u9fff" for ch in english_only)  # no Chinese unless the player typed it


class SlowJudge(Judge):
    name = "slow"

    async def judge(self, state, world, text):
        await asyncio.sleep(5)


class BrokenJudge(Judge):
    name = "broken"

    async def judge(self, state, world, text):
        state.sync = 99  # must not leak out
        raise JudgeError("boom")


@pytest.mark.parametrize("judge,timeout", [(SlowJudge(), 0.05), (BrokenJudge(), 1.0)])
def test_judge_failure_is_silent_and_state_unchanged(content, world, state, judge, timeout):
    before = state.model_dump()
    call = asyncio.run(safe_judge(judge, state, world, "go to the corridor", timeout_s=timeout))
    assert call.ok is False and call.result is None and call.error
    assert state.model_dump() == before
    from app.judge.base import silent_output
    out = silent_output("en", content)
    assert out == [{"kind": "error", "text": "The judge is silent. Nothing happens. Try again."}]
    assert silent_output("zh", content)[0]["text"].startswith("裁判沉默了")


def test_safe_judge_ok(world, state):
    call = asyncio.run(safe_judge(MockJudge(), state, world, "go to the corridor"))
    assert call.ok and call.result.target == "corridor"


def test_judge_mode_falls_back_to_mock(monkeypatch):
    monkeypatch.setenv("JUDGE", "jev")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert judge_mode() == "mock"
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    assert judge_mode() == "mock"  # Jev judge not implemented yet
    assert isinstance(get_judge(), MockJudge)
