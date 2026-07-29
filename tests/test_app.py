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
