"""Judges behind one interface (base.py): OpenRouter Decisions (openrouter.py, the
real judge), TypeSafe Jev (jev.py, kept for when Jev quota exists) and the
keyword mock (mock.py)."""

from __future__ import annotations

import logging
import os

from .base import Judge, JudgeCall, JudgeResult, build_questions, safe_judge, target_options
from .jev import JevJudge
from .mock import MockJudge
from .openrouter import OpenRouterJudge

log = logging.getLogger("fly.judge")

_KEYS = {"openrouter": "OPENROUTER_API_KEY", "jev": "TYPESAFE_API_KEY"}


def judge_mode() -> str:
    """'openrouter' or 'jev' only when asked for and its key is set; else 'mock'."""
    want = os.environ.get("JUDGE", "mock").strip().lower()
    if want in _KEYS:
        if not os.environ.get(_KEYS[want]):
            log.warning("JUDGE=%s but %s is empty; using mock", want, _KEYS[want])
            return "mock"
        if want == "jev" and not JevJudge.implemented:
            log.warning("JUDGE=jev but the Jev judge is not implemented; using mock")
            return "mock"
        return want
    return "mock"


def get_judge() -> Judge:
    mode = judge_mode()
    if mode == "openrouter":
        return OpenRouterJudge()
    if mode == "jev":
        return JevJudge()
    return MockJudge()


__all__ = ["Judge", "JudgeCall", "JudgeResult", "MockJudge", "JevJudge", "OpenRouterJudge",
           "build_questions", "get_judge", "judge_mode", "safe_judge", "target_options"]
