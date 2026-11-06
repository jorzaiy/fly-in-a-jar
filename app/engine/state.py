"""Game state (design §9).

The browser keeps the state in localStorage and sends it with every turn, so
the server is stateless. The model is versioned and capped at 16 KB.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.content.loader import World
from app.content.schema import SYNC_MAX, SYNC_MIN

STATE_VERSION = 2
MAX_STATE_BYTES = 16 * 1024
MAX_RECENT_ACTIONS = 5
MAX_INPUT_CHARS = 200

Lang = Literal["zh", "en"]
Ending = Literal["escaped", "consumed", "absorbed", "disconnected"]


class StateError(ValueError):
    """The state the client sent is unusable (bad shape, wrong version, too big)."""


class RecentAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=MAX_INPUT_CHARS)
    result: str = Field(max_length=32)


class GameState(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    version: Literal[2] = STATE_VERSION
    seed: int = Field(ge=0, lt=2**63)
    turn: int = Field(default=0, ge=0)
    lang: Lang = "en"
    brainlog: bool = True
    scene: str = "reception"
    items: list[str] = Field(default_factory=list, max_length=32)
    taken: list[str] = Field(default_factory=list, max_length=32)
    flags: list[str] = Field(default_factory=list, max_length=32)
    sync: int = Field(default=0, ge=SYNC_MIN, le=SYNC_MAX)
    monster_near: bool = False
    monster_block: int = Field(default=0, ge=0, le=20)
    monster_stunned: int = Field(default=0, ge=0, le=20)
    caught_fly: bool = False
    last_spikes: dict[str, int] = Field(default_factory=dict)
    stim_fatigue: dict[str, int] = Field(default_factory=dict)
    clues_found: list[int] = Field(default_factory=list, max_length=32)
    used_fragments: list[str] = Field(default_factory=list)
    recent_actions: list[RecentAction] = Field(default_factory=list, max_length=MAX_RECENT_ACTIONS)
    ended: Optional[Ending] = None

    @field_validator("last_spikes", "stim_fatigue")
    @classmethod
    def _small_counts(cls, v: dict[str, int]) -> dict[str, int]:
        if len(v) > 32:
            raise ValueError("too many entries")
        for k, n in v.items():
            if len(k) > 32 or n < 0:
                raise ValueError(f"bad entry {k!r}")
        return v

    # ---- helpers -------------------------------------------------------

    def has_flag(self, flag: str) -> bool:
        if flag == "caught_fly":  # also a top-level field (design §9)
            return self.caught_fly
        return flag in self.flags

    def set_flag(self, flag: str) -> None:
        if flag == "caught_fly":
            self.caught_fly = True
        if flag not in self.flags:
            self.flags = [*self.flags, flag]

    def clear_flag(self, flag: str) -> None:
        if flag == "caught_fly":
            self.caught_fly = False
        self.flags = [f for f in self.flags if f != flag]

    def record_action(self, text: str, result: str) -> None:
        acts = [*self.recent_actions, RecentAction(text=text[:MAX_INPUT_CHARS], result=result)]
        self.recent_actions = acts[-MAX_RECENT_ACTIONS:]

    def to_json(self) -> str:
        return self.model_dump_json()

    def size_bytes(self) -> int:
        return len(self.to_json().encode("utf-8"))


def new_state(world: World, seed: int, lang: Lang = "en") -> GameState:
    return GameState(seed=seed, lang=lang, scene=world.start_scene)


def check_refs(state: GameState, world: World) -> None:
    """Reject ids the world does not know (a tampered or stale save)."""
    if state.scene not in world.scenes:
        raise StateError(f"unknown scene {state.scene!r}")
    for i in (*state.items, *state.taken):
        if i not in world.items:
            raise StateError(f"unknown item {i!r}")
    for f in state.flags:
        if f not in world.flags:
            raise StateError(f"unknown flag {f!r}")
    for c in state.clues_found:
        if c not in world.clues:
            raise StateError(f"unknown clue {c!r}")


def parse_state(raw: str | bytes | dict[str, Any], world: World | None = None) -> GameState:
    """Validate a client-sent state. Raises StateError (-> HTTP 400 'restart')."""
    if isinstance(raw, (str, bytes)):
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
        if len(data) > MAX_STATE_BYTES:
            raise StateError(f"state is {len(data)} bytes, limit {MAX_STATE_BYTES}")
        try:
            raw = json.loads(data)
        except ValueError as exc:
            raise StateError(f"state is not JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise StateError("state must be an object")
    if raw.get("version") != STATE_VERSION:
        raise StateError(f"unsupported state version {raw.get('version')!r}")
    if len(json.dumps(raw, ensure_ascii=False).encode("utf-8")) > MAX_STATE_BYTES:
        raise StateError(f"state exceeds {MAX_STATE_BYTES} bytes")
    try:
        state = GameState.model_validate(raw)
    except ValidationError as exc:
        raise StateError(str(exc)) from exc
    if world is not None:
        check_refs(state, world)
    return state


def fit_size(state: GameState) -> GameState:
    """Keep an outgoing state under the cap by forgetting the oldest used fragments.

    `used_fragments` is the only list that grows without bound; dropping its
    oldest entries only means a fragment may repeat sooner.
    """
    while state.size_bytes() > MAX_STATE_BYTES and state.used_fragments:
        drop = max(1, len(state.used_fragments) // 4)
        state.used_fragments = state.used_fragments[drop:]
    if state.size_bytes() > MAX_STATE_BYTES:
        raise StateError("state cannot be shrunk under the size cap")
    return state
