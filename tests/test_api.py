from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JUDGE", "mock")
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["judge"] == "mock"
    assert data["queue"] == 0


def test_new_game(client):
    r = client.post("/api/new", json={"lang": "zh", "seed": 42})
    assert r.status_code == 200
    data = r.json()
    assert "state" in data
    assert data["state"]["seed"] == 42
    assert data["state"]["lang"] == "zh"
    assert len(data["output"]) >= 2


def test_turn_api(client):
    # 1. Start game
    r_new = client.post("/api/new", json={"lang": "en", "seed": 100})
    state = r_new.json()["state"]

    # 2. System command turn
    r_turn1 = client.post("/api/turn", json={"state": state, "input": "look"})
    assert r_turn1.status_code == 200
    res1 = r_turn1.json()
    assert res1["state"]["turn"] == 0

    # 3. Action turn
    r_turn2 = client.post("/api/turn", json={"state": state, "input": "open drawer and take flashlight"})
    assert r_turn2.status_code == 200
    res2 = r_turn2.json()
    assert res2["state"]["turn"] == 1
    assert "flashlight" in res2["state"]["items"]


def test_turn_input_too_long(client):
    r_new = client.post("/api/new", json={"lang": "en", "seed": 100})
    state = r_new.json()["state"]

    long_input = "a" * 250
    r = client.post("/api/turn", json={"state": state, "input": long_input})
    assert r.status_code == 422


def test_static_frontend(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Fly in a Jar" in r.text
    assert "terminal.js" in r.text
