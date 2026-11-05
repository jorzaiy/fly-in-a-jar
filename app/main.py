"""Fly in a Jar — FastAPI entry point.

Run locally:  uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.content.loader import load_content
from app.judge import judge_mode


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to start on bad content, listing every bad fragment id (design §14).
    app.state.content = load_content()
    yield


app = FastAPI(title="Fly in a Jar", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict:
    """Liveness check. Reports which judge is in use, never the key itself."""
    return {"ok": True, "judge": judge_mode(), "queue": 0}
