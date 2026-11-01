"""Fly in a Jar — FastAPI entry point.

Run locally:  uvicorn app.main:app --reload
"""

import os

from fastapi import FastAPI

app = FastAPI(title="Fly in a Jar")


@app.get("/api/health")
def health() -> dict:
    """Liveness check. Reports which judge is configured, never the key itself."""
    judge = os.environ.get("JUDGE", "mock")
    if judge == "jev" and not os.environ.get("TYPESAFE_API_KEY"):
        judge = "mock"  # no key available, fall back
    return {"ok": True, "judge": judge, "queue": 0}
