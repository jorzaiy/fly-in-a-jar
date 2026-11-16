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


def test_new_game_lists_visible_items_and_hud(client):
    data = client.post("/api/new", json={"lang": "zh", "seed": 42}).json()
    listing = [o["text"] for o in data["output"] if o["kind"] == "system"]
    assert listing and "手电筒" in listing[0]
    assert data["hud"] == {"scene": "前台", "sync": 0, "turn": 0, "items": []}


def test_take_shows_taken_line_and_hud_inventory(client):
    state = client.post("/api/new", json={"lang": "en", "seed": 100}).json()["state"]
    res = client.post("/api/turn", json={"state": state, "input": "take flashlight"}).json()
    assert "flashlight" in res["state"]["items"]
    assert any(o["kind"] == "system" and o["text"] == "(Taken: Flashlight)" for o in res["output"])
    assert res["hud"]["items"] == ["Flashlight"]


def test_reading_log_prints_clue_without_extra_action_line(client):
    state = client.post("/api/new", json={"lang": "en", "seed": 100}).json()["state"]
    res = client.post("/api/turn", json={"state": state, "input": "read the visitor log"}).json()
    kinds = [o["kind"] for o in res["output"] if o["kind"] != "brainlog"]
    assert "clue" in kinds
    assert "action" not in kinds


def test_playtest_log_off_by_default(client, tmp_path, monkeypatch):
    monkeypatch.delenv("PLAYTEST_LOG", raising=False)
    r_new = client.post("/api/new", json={"lang": "en", "seed": 7})
    client.post("/api/turn", json={"state": r_new.json()["state"], "input": "take flashlight"})
    assert list(tmp_path.iterdir()) == []


def test_playtest_log_records_input_judge_and_fragments(client, tmp_path, monkeypatch):
    import json
    path = tmp_path / "play.jsonl"
    monkeypatch.setenv("PLAYTEST_LOG", str(path))
    r_new = client.post("/api/new", json={"lang": "en", "seed": 7})
    client.post("/api/turn", json={"state": r_new.json()["state"], "input": "take flashlight"})
    lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert [l["event"] for l in lines] == ["new", "turn"]
    t = lines[1]
    assert t["session"] == 7 and t["input"] == "take flashlight"
    assert t["judge_ok"] is True and t["judge"]["category"] == "take"
    assert t["fragments"] and all(isinstance(f, str) for f in t["fragments"])
    assert t["output"]
