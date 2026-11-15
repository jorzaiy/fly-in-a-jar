"""Decisions judges: OpenRouter Decisions and Command Code System One (tasks.md 2, 10.2).

Jev (TypeSafe / Experiential) has no free quota for this project, so the real
judge is Parallel's `parallel/decisions-fast` model, served through
OpenRouter's Decisions API. It takes the same question types as Jev
(noul / choice / score) and answers the same five questions of design §6.1.

Endpoint (alpha, shape may change):
    POST https://openrouter.ai/api/alpha/decisions
    {"model": ..., "state": <text>, "questions": {id: {...}}}

Response: answers[id] with
    noul   -> .noul (0..1)
    choice -> .choice (+ .probabilities)
    score  -> .probabilities keyed "0".."3"  (argmax is the danger level)
Top-level `annotations` (web citations) are ignored.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from app.content.loader import World
from app.content.schema import CATEGORIES, REASONS, TARGET_NONE
from app.engine.state import GameState

from .base import Judge, JudgeError, JudgeResult, build_questions
from .state_text import state_text

log = logging.getLogger("fly.judge.openrouter")

API_URL = "https://openrouter.ai/api/alpha/decisions"
# The :free variant was withdrawn (404 "unavailable for free") by 2026-11-15.
# Paid slug is about $1 per 1000 requests; override with OPENROUTER_MODEL.
DEFAULT_MODEL = "parallel/decisions-fast"


def to_wire(questions: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map base.build_questions() onto the Decisions API shape:
    choice `options` -> `criteria` object, score `legend` -> ordered `criteria` list."""
    out: dict[str, dict[str, Any]] = {}
    for qid, q in questions.items():
        w: dict[str, Any] = {"type": q["type"], "instructions": q["instructions"]}
        if q["type"] == "choice":
            w["criteria"] = {opt: opt.replace("_", " ") for opt in q["options"]}
        elif q["type"] == "score":
            legend = q["legend"]
            w["criteria"] = [legend[k] for k in sorted(legend, key=int)]
        out[qid] = w
    return out


def _score_level(ans: dict[str, Any]) -> int:
    probs = ans.get("probabilities")
    if isinstance(probs, dict) and probs:
        best = max(probs.items(), key=lambda kv: float(kv[1]))[0]
        return max(0, min(3, int(best)))
    raise JudgeError("danger: no probabilities in answer")


def parse_answers(answers: dict[str, Any], targets: list[str], source: str = "openrouter") -> JudgeResult:
    """Turn raw `answers` into a JudgeResult. Missing or refused answers raise JudgeError
    (the game then says the judge is silent, design §14)."""
    try:
        feasible = float(answers["feasible"]["noul"])
        reason = answers["reason"]["choice"]
        category = answers["category"]["choice"]
        target = answers["target"]["choice"]
        danger = _score_level(answers["danger"])
    except (KeyError, TypeError, ValueError) as exc:
        raise JudgeError(f"bad decisions response: {exc!r}") from exc

    if reason not in REASONS:
        raise JudgeError(f"unknown reason {reason!r}")
    if category not in CATEGORIES:
        category = "other"
    if target not in targets:
        target = TARGET_NONE
    return JudgeResult(
        feasible=max(0.0, min(1.0, feasible)),
        reason=reason,
        category=category,
        target=target,
        danger=danger,
        source=source,
    )


class OpenRouterJudge(Judge):
    name = "openrouter"
    implemented = True
    url = API_URL
    key_env = "OPENROUTER_API_KEY"
    model_env = "OPENROUTER_MODEL"
    default_model = DEFAULT_MODEL

    def __init__(self, api_key: str | None = None, model: str | None = None,
                 client: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key or os.environ.get(self.key_env)
        if not self.api_key:
            raise JudgeError(f"{self.key_env} environment variable is not set")
        self.model = model or os.environ.get(self.model_env, self.default_model)
        # safe_judge() enforces the 6 s game timeout; this is only a backstop.
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def judge(self, state: GameState, world: World, text: str) -> JudgeResult:
        questions = build_questions(state, world)
        targets = questions["target"]["options"]
        body = {
            "model": self.model,
            "state": state_text(state, world, text),
            "questions": to_wire(questions),
        }
        try:
            r = await self._client.post(
                self.url, json=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/jorzaiy/fly-in-a-jar",
                    "X-Title": "Fly in a Jar",
                },
            )
        except httpx.HTTPError as exc:
            raise JudgeError(f"network: {type(exc).__name__}") from exc
        if r.status_code != 200:
            raise JudgeError(f"HTTP {r.status_code}")
        data = r.json()
        return parse_answers(data.get("answers") or {}, targets, source=self.name)


class CommandCodeJudge(OpenRouterJudge):
    """TypeSafe Jev through Command Code's Provider API (System One shape, same
    questions and answers as above). Needs a Command Code plan with API access
    (every plan except Go)."""

    name = "commandcode"
    url = "https://api.commandcode.ai/provider/v1/systemone"
    key_env = "COMMANDCODE_API_KEY"
    model_env = "COMMANDCODE_MODEL"
    default_model = "typesafe/jev"


class GeminiJudge(OpenRouterJudge):
    """Google Gemini Decision 1 via the Gemini Decisions API (v1beta, launched
    2026-11-11). Same noul/choice/score questions; the shared text goes in
    `input` instead of `state`, and the key in `x-goog-api-key`. Free tier:
    200 rpm, 10,000 requests/day per project, no billing needed. A request
    blocked by Google's safety filter returns 400 and the judge goes silent."""

    name = "gemini"
    url = "https://generativelanguage.googleapis.com/v1beta/decisions"
    key_env = "GEMINI_API_KEY"
    model_env = "GEMINI_DECISION_MODEL"
    default_model = "gemini-decision-1"

    async def judge(self, state: GameState, world: World, text: str) -> JudgeResult:
        questions = build_questions(state, world)
        targets = questions["target"]["options"]
        body = {
            "model": self.model,
            "input": state_text(state, world, text),
            "questions": to_wire(questions),
        }
        try:
            r = await self._client.post(self.url, json=body,
                                        headers={"x-goog-api-key": self.api_key})
        except httpx.HTTPError as exc:
            raise JudgeError(f"network: {type(exc).__name__}") from exc
        if r.status_code != 200:
            raise JudgeError(f"HTTP {r.status_code}")
        return parse_answers(r.json().get("answers") or {}, targets, source=self.name)
