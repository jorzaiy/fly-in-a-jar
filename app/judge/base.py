"""Judge interface (design §6).

Both judges (the real Jev API and the local keyword mock) answer the same five
questions of design §6.1 and return the same `JudgeResult`. The engine only
ever sees `JudgeResult` (via `safe_judge`), so `jev.py` can drop in without
touching anything else.

Raw Jev field names are not verified yet (tasks.md 2.3). `JudgeResult` is the
contract; `jev.py` is responsible for mapping the raw response onto it.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.content.loader import World
from app.content.schema import CATEGORIES, REASONS, TARGET_MONSTER, TARGET_NONE
from app.engine.rules import visible_targets
from app.engine.state import GameState

log = logging.getLogger("fly.judge")

Reason = Literal[
    "physically_impossible", "missing_item", "no_such_target",
    "against_world_rules", "not_an_action", "feasible",
]
Category = Literal[
    "look", "move", "take", "use", "eat", "smell", "listen",
    "touch", "light", "attack", "hide", "wait", "talk", "other",
]


class JudgeResult(BaseModel):
    """Answers to the five questions of design §6.1, keyed by question id."""

    feasible: float = Field(ge=0.0, le=1.0)   # Noul: probability the action can be done
    reason: Reason                            # Choice
    category: Category                        # Choice
    target: str                               # Choice, options from target_options()
    danger: int = Field(ge=0, le=3)           # Score: 0 safe, 1 risky, 2 dangerous, 3 suicidal
    source: Literal["jev", "mock"] = "mock"


# --------------------------------------------------------------------- questions (design §6.1)


def target_options(state: GameState, world: World) -> list[str]:
    """Dynamic `target` choices: exits, visible items, fixtures, inventory, monster, none."""
    v = visible_targets(state, world)
    opts: list[str] = []
    for group in ("exits", "items_here", "fixtures", "inventory"):
        for t in v[group]:
            if t not in opts:
                opts.append(t)
    return [*opts, TARGET_MONSTER, TARGET_NONE]


def build_questions(state: GameState, world: World) -> dict[str, dict[str, Any]]:
    """The question set sent to Jev, in English. Shapes follow research.md and
    are re-checked against the real SDK in tasks.md 2.3."""
    return {
        "feasible": {
            "type": "noul",
            "instructions": "Can the player perform this action now, given the scene, the inventory "
                            "and the world rules?",
        },
        "reason": {
            "type": "choice",
            "instructions": "If the action cannot be performed, why not? Pick 'feasible' if it can.",
            "options": list(REASONS),
        },
        "category": {
            "type": "choice",
            "instructions": "What kind of action is this?",
            "options": list(CATEGORIES),
        },
        "target": {
            "type": "choice",
            "instructions": "What does the action act on? Use 'monster' for the swarm and 'none' if "
                            "nothing specific.",
            "options": target_options(state, world),
        },
        "danger": {
            "type": "score",
            "instructions": "How dangerous is this action for the player?",
            "legend": {"0": "safe", "1": "risky", "2": "dangerous", "3": "suicidal"},
        },
    }


def normalize(result: JudgeResult, options: list[str]) -> JudgeResult:
    """Force `target` into the offered options (anything else becomes 'none')."""
    if result.target not in options:
        return result.model_copy(update={"target": TARGET_NONE})
    return result


# --------------------------------------------------------------------- interface


class JudgeError(Exception):
    """The judge could not answer (network, quota, bad response)."""


class Judge(ABC):
    name: str = "judge"

    @abstractmethod
    async def judge(self, state: GameState, world: World, text: str) -> JudgeResult:
        """Answer the five questions for `text` in `state`. May raise JudgeError."""


@dataclass
class JudgeCall:
    ok: bool
    result: Optional[JudgeResult] = None
    error: Optional[str] = None
    ms: int = 0


async def safe_judge(judge: Judge, state: GameState, world: World, text: str,
                     timeout_s: float = 6.0) -> JudgeCall:
    """Call a judge with a hard timeout and no retry (design §6.4).

    On timeout or any error the caller shows 'the judge is silent' and leaves
    the state untouched, with no sync penalty (design §14, tasks.md 10.5).
    The state passed in is never mutated here.
    """
    t0 = time.perf_counter()
    snapshot = state.model_copy(deep=True)
    try:
        result = await asyncio.wait_for(judge.judge(snapshot, world, text), timeout=timeout_s)
        result = normalize(result, target_options(state, world))
        return JudgeCall(ok=True, result=result, ms=int((time.perf_counter() - t0) * 1000))
    except asyncio.TimeoutError:
        err = "timeout"
    except Exception as exc:  # noqa: BLE001  any judge failure is the same to the player
        err = f"{type(exc).__name__}"
    ms = int((time.perf_counter() - t0) * 1000)
    log.warning("judge %s failed: %s after %d ms", judge.name, err, ms)
    return JudgeCall(ok=False, error=err, ms=ms)


def silent_output(lang: str, content) -> list[dict[str, str]]:
    """The in-game line for a failed judge call."""
    return [{"kind": "error", "text": content.text("errors.judge_silent", lang)}]
