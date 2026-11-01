"""The live server's reload and session state: the paths that run while a
room is watching, where a bug costs the most."""

import json
import time

from fastapi.testclient import TestClient

from glissade.app import create_app, load_live_notes, load_settings
from glissade.project import find_project


def _deck(title, n):
    return {"title": title, "slides": [
        {"layout": "title", "heading": f"{title} {i}", "notes": "n"} for i in range(1, n + 1)
    ]}


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_shrinking_deck_keeps_position_in_range(tmp_path, sample_deck_file):
    app = create_app(find_project(tmp_path))
    client = TestClient(app)
    client.post("/api/goto", json={"n": 2})
    _write(sample_deck_file, _deck("Short", 1))
    state = app.state.reload_project()
    assert state["total"] == 1 and state["n"] == 1


def test_deleting_the_open_deck_falls_back_to_another(tmp_path, sample_deck_file):
    _write(tmp_path / "decks" / "other.json", _deck("Other", 3))
    app = create_app(find_project(tmp_path), "talk")
    assert app.state.show.deck == "talk"
    sample_deck_file.unlink()
    state = app.state.reload_project()
    assert state["deck"] == "other" and state["total"] == 3


def test_removed_theme_falls_back_to_a_real_one(tmp_path, sample_deck_file):
    themes = tmp_path / "themes.json"
    _write(themes, [
        {"id": "one", "name": "One", "vars": {}},
        {"id": "two", "name": "Two", "vars": {}},
    ])
    app = create_app(find_project(tmp_path))
    client = TestClient(app)
    assert client.post("/api/theme", json={"id": "two"}).json()["theme"] == "two"
    _write(themes, [{"id": "one", "name": "One", "vars": {}}])
    assert app.state.reload_project()["theme"] == "one"


def test_switching_decks_resets_position_and_bumps_rev(tmp_path, sample_deck_file):
    _write(tmp_path / "decks" / "other.json", _deck("Other", 3))
    client = TestClient(create_app(find_project(tmp_path), "talk"))
    client.post("/api/goto", json={"n": 2})
    state = client.post("/api/deck", json={"id": "other"}).json()
    assert (state["deck"], state["n"], state["total"], state["rev"]) == ("other", 1, 3, 1)
    # Unknown ids and the current deck change nothing.
    assert client.post("/api/deck", json={"id": "nope"}).json()["rev"] == 1
    assert client.post("/api/deck", json={"id": "other"}).json()["rev"] == 1


def test_settings_and_live_notes_survive_a_restart(tmp_path, sample_deck_file):
    project = find_project(tmp_path)
    client = TestClient(create_app(project))
    client.post("/api/scale", json={"scale": 1.3})
    client.post("/api/live-notes", json={"text": "follow up with finance", "n": 2})

    again = TestClient(create_app(project)).get("/api/state").json()
    assert again["scale"] == 1.3
    assert again["all_live_notes"] == [{"n": 2, "text": "follow up with finance"}]


def test_corrupt_state_files_fall_back_to_defaults(tmp_path):
    state = tmp_path / "state.json"
    state.write_text("{oops", encoding="utf-8")
    assert load_settings(state, ["a"], ["d"]) == {"scale": 1.0, "theme": "a", "deck": "d"}
    _write(state, {"scale": 99, "theme": "gone", "deck": "gone"})
    assert load_settings(state, ["a"], ["d"]) == {"scale": 1.6, "theme": "a", "deck": "d"}

    notes = tmp_path / "notes.json"
    _write(notes, {"deck": {"1": "keep", "2": "   "}, "bad": "not a dict"})
    assert load_live_notes(notes) == {"deck": {"1": "keep"}}


def test_watcher_reloads_on_change_and_reports_broken_json(tmp_path, sample_deck_file):
    app = create_app(
        find_project(tmp_path), watch=True, watch_interval=0.02, watch_debounce=0.02
    )

    def wait_for(predicate, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return False

    with TestClient(app) as client:  # the context runs the lifespan, so the watcher
        _write(sample_deck_file, _deck("Edited", 4))
        assert wait_for(lambda: client.get("/api/state").json()["total"] == 4)
        assert client.get("/api/state").json()["rev"] == 1

        sample_deck_file.write_text("{ half written", encoding="utf-8")
        assert wait_for(lambda: client.get("/api/state").json()["reload_error"])
        state = client.get("/api/state").json()
        assert state["total"] == 4 and state["rev"] == 1   # last good deck stays up

        _write(sample_deck_file, _deck("Fixed", 2))
        assert wait_for(lambda: client.get("/api/state").json()["total"] == 2)
        assert client.get("/api/state").json()["reload_error"] == ""
