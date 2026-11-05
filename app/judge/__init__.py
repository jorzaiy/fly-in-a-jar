"""Judges: the Jev API (jev.py) and the keyword mock (mock.py), behind one interface (base.py)."""

from __future__ import annotations

import logging
import os

from .base import Judge, JudgeCall, JudgeResult, build_questions, safe_judge, target_options
from .jev import JevJudge
from .mock import MockJudge

log = logging.getLogger("fly.judge")


def judge_mode() -> str:
    """'jev' only when asked for, a key is set and the Jev judge exists; else 'mock'."""
    want = os.environ.get("JUDGE", "mock").strip().lower()
    if want == "jev":
        if not os.environ.get("TYPESAFE_API_KEY"):
            log.warning("JUDGE=jev but TYPESAFE_API_KEY is empty; using mock")
            return "mock"
        if not JevJudge.implemented:
            log.warning("JUDGE=jev but the Jev judge is not implemented yet; using mock")
            return "mock"
        return "jev"
    return "mock"


def get_judge() -> Judge:
    return JevJudge() if judge_mode() == "jev" else MockJudge()


__all__ = ["Judge", "JudgeCall", "JudgeResult", "MockJudge", "JevJudge", "build_questions",
           "get_judge", "judge_mode", "safe_judge", "target_options"]
