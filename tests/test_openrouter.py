import asyncio

import httpx
import pytest

from app.judge import OpenRouterJudge, build_questions, get_judge, judge_mode, safe_judge
from app.judge.base import JudgeError
from app.judge.openrouter import API_URL, parse_answers, to_wire


def _answers(target="flashlight", reason="feasible"):
    return {
        "feasible": {"type": "noul", "noul": 0.91},
        "reason": {"type": "choice", "choice": reason, "probabilities": {reason: 0.9}},
        "category": {"type": "choice", "choice": "take"},
        "target": {"type": "choice", "choice": target},
        "danger": {"type": "score", "score": 0.1, "probabilities": {"0": 0.7, "1": 0.2, "2": 0.1, "3": 0.0}},
    }


def test_to_wire_shapes(world, state):
    w = to_wire(build_questions(state, world))
    assert w["feasible"] == {"type": "noul", "instructions": w["feasible"]["instructions"]}
    assert isinstance(w["category"]["criteria"], dict) and "take" in w["category"]["criteria"]
    assert w["danger"]["criteria"] == ["safe", "risky", "dangerous", "suicidal"]
    assert all("options" not in q and "legend" not in q for q in w.values())


def test_parse_answers(world, state):
    targets = build_questions(state, world)["target"]["options"]
    r = parse_answers(_answers(), targets)
    assert (r.category, r.target, r.reason, r.danger, r.source) == ("take", "flashlight", "feasible", 0, "openrouter")
    assert parse_answers(_answers(target="moon"), targets).target == "none"


def test_parse_answers_danger_argmax(world, state):
    targets = build_questions(state, world)["target"]["options"]
    a = _answers()
    a["danger"]["probabilities"] = {"0": 0.1, "1": 0.2, "2": 0.25, "3": 0.45}
    assert parse_answers(a, targets).danger == 3


@pytest.mark.parametrize("drop", ["feasible", "danger"])
def test_parse_answers_missing_raises(world, state, drop):
    a = _answers()
    a.pop(drop)
    with pytest.raises(JudgeError):
        parse_answers(a, build_questions(state, world)["target"]["options"])


def _judge(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenRouterJudge(api_key="test", client=client)


def test_judge_roundtrip(world, state):
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["authorization"]
        return httpx.Response(200, json={"answers": _answers(), "annotations": []})

    call = asyncio.run(safe_judge(_judge(handler), state, world, "take the flashlight"))
    assert call.ok and call.result.source == "openrouter"
    assert seen == {"url": API_URL, "auth": "Bearer test"}


def test_judge_http_error_is_silent(world, state):
    call = asyncio.run(safe_judge(_judge(lambda r: httpx.Response(402, json={})), state, world, "x"))
    assert not call.ok


def test_judge_mode_openrouter(monkeypatch):
    monkeypatch.setenv("JUDGE", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert judge_mode() == "mock"
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    assert judge_mode() == "openrouter"
    assert isinstance(get_judge(), OpenRouterJudge)
