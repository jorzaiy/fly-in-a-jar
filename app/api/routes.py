"""FastAPI API routes for Fly in a Jar (tasks.md 12.3, 12.4, 12.5 & design §9).

Provides:
- GET /api/health
- POST /api/new
- POST /api/turn
Includes in-memory IP rate limiting, concurrency semaphore, and JSON logging.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
import json
import logging
import secrets
import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.brain.groups import BrainGroups
from app.brain.lif import LIFSimulator
from app.content.loader import Content
from app.engine.rules import items_here
from app.engine.state import GameState, Lang, MAX_INPUT_CHARS, new_state
from app.engine.turn import execute_turn
from app.judge import get_judge, judge_mode
from app.narrator.compose import resolve_fragment_text
from app.narrator.select import fragment_trace, select_fragment
from app.api.playtest import playtest_path, write_playtest

log = logging.getLogger("fly.api")

router = APIRouter(prefix="/api")

# Rate limiting: max 20 turns per minute per IP (design §9.11)
RATE_LIMIT_TURNS = 20
RATE_LIMIT_WINDOW_S = 60.0
_ip_turn_history: dict[str, list[float]] = defaultdict(list)

# Concurrency limits: max 2 concurrent simulations, queue capacity 8 (design §5.2)
MAX_CONCURRENT_SIMS = 2
MAX_QUEUE_WAITING = 8
_sim_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SIMS)
_waiting_count = 0


def check_rate_limit(client_ip: str) -> None:
    now = time.time()
    history = _ip_turn_history[client_ip]
    # Remove timestamps older than 60s
    valid = [t for t in history if now - t < RATE_LIMIT_WINDOW_S]
    _ip_turn_history[client_ip] = valid

    if len(valid) >= RATE_LIMIT_TURNS:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit", "message": "Too many requests. Please slow down."},
        )
    valid.append(now)


class NewGameRequest(BaseModel):
    lang: Lang = "en"
    seed: Optional[int] = None


class TurnRequest(BaseModel):
    state: GameState
    input: str = Field(max_length=MAX_INPUT_CHARS)


def hud(state: GameState, world: Any, lang: str) -> dict[str, Any]:
    """Always-visible status: scene, sync, turn and what the player carries."""
    return {
        "scene": world.scenes.get(state.scene, {}).get("name", {}).get(lang, state.scene),
        "sync": state.sync,
        "turn": state.turn,
        "items": [world.items[i]["name"][lang] for i in state.items if i in world.items],
    }


@router.get("/health")
def health() -> dict[str, Any]:
    """Liveness check reporting judge mode and simulation queue size."""
    global _waiting_count
    return {
        "ok": True,
        "judge": judge_mode(),
        "queue": _waiting_count,
    }


@router.post("/new")
def new_game(req: NewGameRequest, request: Request) -> dict[str, Any]:
    """Start a new game session and return opening narrative."""
    content: Content = request.app.state.content
    seed = req.seed if req.seed is not None else secrets.randbelow(2**31)
    state = new_state(content.world, seed=seed, lang=req.lang)

    # Opening narrative fragment
    opening_frag = select_fragment("opening", "default", 0, state, content, spike_count=0)
    opening_text = resolve_fragment_text(opening_frag, state, req.lang, None, content.world, content)

    # Scene enter description
    scene_frag = select_fragment("scene_enter", state.scene, 0, state, content, spike_count=0)
    scene_text = resolve_fragment_text(scene_frag, state, req.lang, None, content.world, content)

    # Scene listing
    sc_info = content.world.scenes.get(state.scene, {})
    exits = sc_info.get("exits", [])
    exit_names = [content.world.scenes[e]["name"][req.lang] for e in exits if e in content.world.scenes]
    items_names = [content.world.items[it]["name"][req.lang] for it in items_here(state, content.world) if it in content.world.items]

    listing_parts = []
    if exit_names:
        exits_title = "出口" if req.lang == "zh" else "Exits"
        listing_parts.append(f"{exits_title}: {', '.join(exit_names)}")
    if items_names:
        items_title = "可见物品" if req.lang == "zh" else "Visible items"
        listing_parts.append(f"{items_title}: {', '.join(items_names)}")

    output = [
        {"kind": "narrative", "text": opening_text},
        {"kind": "scene", "text": scene_text},
    ]
    if listing_parts:
        output.append({"kind": "system", "text": " | ".join(listing_parts)})

    if playtest_path():
        write_playtest({
            "event": "new", "session": state.seed, "lang": req.lang,
            "scene": state.scene, "output": output,
        })

    return {
        "state": state.model_dump(),
        "output": output,
        "ended": None,
        "hud": hud(state, content.world, req.lang),
    }


@router.post("/turn")
async def turn_endpoint(req: TurnRequest, request: Request) -> dict[str, Any]:
    """Process a player action, execute simulation, and advance game state."""
    global _waiting_count

    # 1. IP Rate Limiting
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    # 2. Concurrency queue check
    if _waiting_count >= MAX_QUEUE_WAITING:
        raise HTTPException(
            status_code=503,
            detail={"error": "overloaded", "message": "Brain simulation queue is full. Try again shortly."},
        )

    content: Content = request.app.state.content
    brain_groups: BrainGroups = request.app.state.brain_groups
    simulator: LIFSimulator = request.app.state.simulator
    judge = get_judge()

    _waiting_count += 1
    t0 = time.perf_counter()
    frag_ids: list[str] = []
    trace_token = fragment_trace.set(frag_ids)
    scene_before = req.state.scene
    try:
        async with _sim_semaphore:
            turn_res = await execute_turn(
                state=req.state,
                player_input=req.input,
                world=content.world,
                content=content,
                judge=judge,
                brain_groups=brain_groups,
                simulator=simulator,
            )
    finally:
        _waiting_count -= 1
        fragment_trace.reset(trace_token)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # Output JSON structured log line (design §9.10: no API keys or raw user input)
    log_record = {
        "turn": turn_res.state.turn,
        "scene": turn_res.state.scene,
        "sync": turn_res.state.sync,
        "ended": turn_res.ended,
        "duration_ms": elapsed_ms,
    }
    print(json.dumps(log_record, ensure_ascii=False))

    if playtest_path():
        write_playtest({
            "event": "turn", "session": turn_res.state.seed, "lang": turn_res.state.lang,
            "turn": turn_res.state.turn, "scene_before": scene_before,
            "scene": turn_res.state.scene, "sync": turn_res.state.sync,
            "input": req.input, "system_command": turn_res.is_system_command,
            **turn_res.trace, "fragments": frag_ids,
            "output": turn_res.output, "ended": turn_res.ended, "duration_ms": elapsed_ms,
        })

    return {
        "state": turn_res.state.model_dump(),
        "output": turn_res.output,
        "ended": turn_res.ended,
        "hud": hud(turn_res.state, content.world, turn_res.state.lang),
    }
