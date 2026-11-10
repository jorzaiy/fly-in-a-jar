"""Jev judge implementation using official typesafe-sdk (tasks.md 10.2).

Calls TypeSafe AI's Jev model with the 5 questions defined in design §6.1,
mapping the answers onto `JudgeResult`.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score
from typesafe_sdk import TypeSafeAPIError

from app.content.loader import World
from app.content.schema import CATEGORIES, REASONS, TARGET_NONE
from app.engine.state import GameState

from .base import Judge, JudgeError, JudgeResult, target_options
from .state_text import state_text

log = logging.getLogger("fly.judge.jev")


class JevJudge(Judge):
    name = "jev"
    implemented = True

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        if not self.api_key:
            raise JudgeError("TYPESAFE_API_KEY environment variable is not set")
        self._client = AsyncTypeSafeClient(api_key=self.api_key)

    async def judge(self, state: GameState, world: World, text: str) -> JudgeResult:
        st_text = state_text(state, world, text)
        targets = target_options(state, world)

        questions = {
            "feasible": Noul(
                instructions="Can the player perform this action now, given the scene, inventory, and world rules?"
            ),
            "reason": Choice(
                instructions="If the action cannot be performed, why not? Pick 'feasible' if it can.",
                criteria={opt: None for opt in REASONS},
            ),
            "category": Choice(
                instructions="What kind of action is this?",
                criteria={opt: None for opt in CATEGORIES},
            ),
            "target": Choice(
                instructions="What does the action act on? Use 'monster' for the swarm and 'none' if nothing specific.",
                criteria={t: None for t in targets},
            ),
            "danger": Score(
                instructions="How dangerous is this action for the player?",
                criteria=["safe", "risky", "dangerous", "suicidal"],
            ),
        }

        try:
            resp = await self._client.system_one(
                state={"environment": st_text, "action": text},
                questions=questions,
            )
            answers = resp.answers

            # Parse feasible
            feasible_ans = answers.get("feasible")
            feasible_val = float(feasible_ans.noul) if hasattr(feasible_ans, "noul") else 0.0

            # Parse reason
            reason_ans = answers.get("reason")
            reason_val = getattr(reason_ans, "choice", "against_world_rules")
            if reason_val not in REASONS:
                reason_val = "feasible" if feasible_val >= 0.65 else "against_world_rules"

            # Parse category
            cat_ans = answers.get("category")
            cat_val = getattr(cat_ans, "choice", "other")
            if cat_val not in CATEGORIES:
                cat_val = "other"

            # Parse target
            target_ans = answers.get("target")
            target_val = getattr(target_ans, "choice", TARGET_NONE)
            if target_val not in targets:
                target_val = TARGET_NONE

            # Parse danger (score in typesafe-sdk is float expected score)
            danger_ans = answers.get("danger")
            if hasattr(danger_ans, "score") and danger_ans.score is not None:
                danger_val = int(round(float(danger_ans.score)))
            else:
                danger_val = 0
            danger_val = max(0, min(3, danger_val))

            return JudgeResult(
                feasible=max(0.0, min(1.0, feasible_val)),
                reason=reason_val,
                category=cat_val,
                target=target_val,
                danger=danger_val,
                source="jev",
            )
        except TypeSafeAPIError as exc:
            log.warning("TypeSafe API error: %s", exc)
            raise JudgeError(f"TypeSafe API error: {exc}") from exc
        except Exception as exc:
            log.warning("Jev judge error: %s", exc)
            raise JudgeError(f"Jev call failed: {exc}") from exc
