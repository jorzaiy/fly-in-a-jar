"""Jev judge (tasks.md 10.2): NOT IMPLEMENTED YET.

Waits on tasks.md 2 (verify the typesafe-sdk request/response fields with a
real key). When it lands it must:
  - send `state_text(...)` as the state and `build_questions(...)` as the questions,
  - map the raw response onto `JudgeResult` (base.py),
  - time out after `RulesConfig.judge_timeout_s` with no retry,
  - read the key only from TYPESAFE_API_KEY.
Until then `get_judge()` never selects it.
"""

from __future__ import annotations

from app.content.loader import World
from app.engine.state import GameState

from .base import Judge, JudgeError, JudgeResult


class JevJudge(Judge):
    name = "jev"
    implemented = False

    async def judge(self, state: GameState, world: World, text: str) -> JudgeResult:
        raise JudgeError("Jev judge not implemented yet (tasks.md 10.2)")
