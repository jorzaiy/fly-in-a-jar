"""Fly in a Jar — FastAPI entry point.

Run locally:  uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.brain.groups import BrainGroups
from app.brain.lif import LIFSimulator
from app.content.loader import load_content
from app.judge import get_judge

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to start on bad content, listing every bad fragment id (design §14).
    app.state.content = load_content()
    app.state.brain_groups = BrainGroups()
    app.state.simulator = LIFSimulator()
    app.state.judge = get_judge()
    yield


app = FastAPI(title="Fly in a Jar", lifespan=lifespan)
app.include_router(api_router)

# Mount static frontend
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
