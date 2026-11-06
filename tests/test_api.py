from fastapi.testclient import TestClient

from app.main import app


def test_health(monkeypatch):
    monkeypatch.setenv("JUDGE", "mock")
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True, "judge": "mock", "queue": 0}
        assert app.state.content.fragments
