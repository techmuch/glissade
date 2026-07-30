import json

from fastapi.testclient import TestClient

from glissade.app import clamp_scale, create_app
from glissade.project import find_project


def test_clamp_scale():
    assert clamp_scale(1.0) == 1.0
    assert clamp_scale(0.5) == 0.7   # clamped to MIN_SCALE
    assert clamp_scale(2.5) == 1.6   # clamped to MAX_SCALE
    assert clamp_scale("invalid") == 1.0

def test_app_routes(tmp_path, sample_deck_file):
    project = find_project(tmp_path)
    app = create_app(project)
    client = TestClient(app)

    # 1. Main deck view
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Glissade" in resp.text
    assert "<!DOCTYPE html>" in resp.text

    # 2. Control view
    resp = client.get("/control")
    assert resp.status_code == 200
    assert "Live notes" in resp.text

    # 3. Next slide API
    resp = client.post("/api/next")
    assert resp.status_code == 200
    data = resp.json()
    assert data["n"] == 2

    # 4. Previous slide API
    resp = client.post("/api/prev")
    assert resp.status_code == 200
    data = resp.json()
    assert data["n"] == 1

    # 5. Blank API
    resp = client.post("/api/blank", json={"blank": True})
    assert resp.status_code == 200
    assert resp.json()["blank"] is True

    # 6. Live notes API
    resp = client.post("/api/live-notes", json={"n": 1, "text": "Remember to speak clearly."})
    assert resp.status_code == 200
    assert resp.json()["live_note"] == "Remember to speak clearly."
    assert len(resp.json().get("all_live_notes", [])) == 1
    assert resp.json()["all_live_notes"][0] == {"n": 1, "text": "Remember to speak clearly."}

    # 7. GET /api/live-notes
    resp = client.get("/api/live-notes")
    assert resp.status_code == 200
    notes_data = resp.json()
    assert notes_data["text"] == "Remember to speak clearly."
    assert len(notes_data["all"]) == 1
    assert notes_data["all"][0] == {"n": 1, "text": "Remember to speak clearly."}


def test_reload_project_state_refreshes_slides_and_bumps_rev(tmp_path, sample_deck_file):
    project = find_project(tmp_path)
    app = create_app(project)
    client = TestClient(app)

    before = client.get("/api/state").json()
    assert before["rev"] == 0
    assert before["reload_error"] == ""

    deck_path = sample_deck_file
    data = json.loads(deck_path.read_text(encoding="utf-8"))
    data["slides"][0]["heading"] = "Fresh heading from disk"
    data["slides"].append(
        {
            "title": "New ending",
            "layout": "title",
            "heading": "Thanks",
            "body": "<p>Reloaded.</p>",
            "notes": "Wrap up.",
        }
    )
    deck_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    app.state.reload_project()

    after = client.get("/api/state").json()
    assert after["rev"] == 1
    assert after["total"] == 3
    assert after["reload_error"] == ""

    slides = client.get("/api/slides").json()
    assert slides[0]["heading"] == "Fresh heading from disk"
    assert slides[-1]["heading"] == "Thanks"


def test_reload_project_state_keeps_last_good_deck_on_invalid_json(tmp_path, sample_deck_file):
    project = find_project(tmp_path)
    app = create_app(project)
    client = TestClient(app)

    sample_deck_file.write_text("{ not valid json", encoding="utf-8")

    before = client.get("/api/slides").json()
    state = client.get("/api/state").json()
    assert state["rev"] == 0

    try:
        app.state.reload_project()
    except ValueError as exc:
        app.state.show.reload_error = str(exc)
        app.state.show.publish()

    after = client.get("/api/slides").json()
    state = client.get("/api/state").json()
    assert after == before
    assert state["rev"] == 0
    assert "can't reload until these deck files parse again" in state["reload_error"]
