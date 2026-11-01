"""Themes defined inside a deck file, and `extends` between themes."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from glissade.app import create_app, load_themes
from glissade.build import build_deck
from glissade.check import check_deck, check_themes
from glissade.cli import main
from glissade.decks import read_deck
from glissade.project import DEFAULT_THEMES, find_project
from glissade.themes import deck_theme, for_deck, load

PALETTE = {"dark": "#1b2a41", "light": "#f7f4ee", "accent": "#c8553d"}


def _deck(tmp_path, name="talk", theme=None, **extra):
    decks = tmp_path / "decks"
    decks.mkdir(exist_ok=True)
    body = {"title": name.title(), "slides": [
        {"layout": "title", "heading": "Hello", "notes": "n"},
        {"layout": "title", "heading": "Again", "notes": "n"},
    ], **extra}
    if theme is not None:
        body["theme"] = theme
    path = decks / f"{name}.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _vars(theme_list, theme_id):
    return next(t for t in theme_list if t["id"] == theme_id)["vars"]


# ---------------------------------------------------------------- reading


def test_string_theme_is_unchanged(tmp_path):
    deck = read_deck(_deck(tmp_path, theme="parchment"))
    assert deck["theme"] == "parchment" and deck["theme_spec"] is None


def test_object_theme_gets_a_deck_scoped_id(tmp_path):
    deck = read_deck(_deck(tmp_path, theme={"palette": PALETTE}))
    assert deck["theme"] == "deck:talk"
    assert deck["theme_spec"] == {"palette": PALETTE}


# ---------------------------------------------------------------- expansion


def test_palette_expands_and_vars_win(tmp_path):
    deck = read_deck(_deck(tmp_path, theme={
        "name": "Q3", "palette": PALETTE, "vars": {"--card-bg": "#ffffff"}}))
    t = deck_theme(deck, load_themes(), DEFAULT_THEMES)
    assert t["id"] == "deck:talk" and t["name"] == "Q3 (this deck)"
    assert t["vars"]["--paper"] == "#f7f4ee"
    assert t["vars"]["--card-bg"] == "#ffffff"


def test_name_defaults_to_the_deck_title(tmp_path):
    deck = read_deck(_deck(tmp_path, theme={"palette": PALETTE}))
    assert deck_theme(deck, [], None)["name"] == "Talk (this deck)"


def test_extends_inherits_what_it_does_not_override(tmp_path):
    shared = load_themes()
    parchment = _vars(shared, "parchment")
    deck = read_deck(_deck(tmp_path, theme={
        "extends": "parchment", "vars": {"--accent": "#123456"}}))
    t = deck_theme(deck, shared, DEFAULT_THEMES)
    assert t["vars"]["--accent"] == "#123456"
    assert t["vars"]["--paper"] == parchment["--paper"]
    assert "_extends_error" not in t


def test_extends_falls_back_to_built_in_themes(tmp_path):
    # A project whose themes.json lacks "paper" can still extend it.
    deck = read_deck(_deck(tmp_path, theme={"extends": "paper"}))
    t = deck_theme(deck, [{"id": "mine", "vars": {}}], DEFAULT_THEMES)
    assert "_extends_error" not in t and t["vars"]


def test_unknown_extends_is_recorded(tmp_path):
    deck = read_deck(_deck(tmp_path, theme={"extends": "papr", "palette": PALETTE}))
    t = deck_theme(deck, load_themes(), DEFAULT_THEMES)
    assert "isn't a theme" in t["_extends_error"]
    assert t["vars"]["--paper"] == "#f7f4ee"   # its own palette still applies


def test_deck_fonts_resolve_beside_the_deck(tmp_path):
    path = _deck(tmp_path, theme={"palette": PALETTE,
                                  "fonts": [{"family": "Mine", "src": "fonts/mine.woff2"}]})
    t = deck_theme(read_deck(path), [], None)
    assert t["fonts"][0]["path"] == str(path.parent.resolve() / "fonts" / "mine.woff2")


def test_for_deck_puts_the_deck_theme_first(tmp_path):
    shared = load_themes()
    deck = read_deck(_deck(tmp_path, theme={"palette": PALETTE}))
    offered = [t["id"] for t in for_deck(shared, deck, DEFAULT_THEMES)]
    assert offered == ["deck:talk", *[t["id"] for t in shared]]
    plain = read_deck(_deck(tmp_path, name="plain"))
    assert for_deck(shared, plain) == shared


# ------------------------------------------------------- themes.json extends


def test_themes_json_entries_can_extend_each_other_and_built_ins(tmp_path):
    source = tmp_path / "themes.json"
    source.write_text(json.dumps([
        {"id": "child", "name": "Child", "extends": "base", "vars": {"--ink": "#000000"}},
        {"id": "base", "name": "Base", "extends": "parchment", "vars": {"--rule": "#abcdef"}},
    ]), encoding="utf-8")
    themes = {t["id"]: t for t in load(source, builtin=DEFAULT_THEMES)}
    parchment = _vars(load(DEFAULT_THEMES), "parchment")
    child = themes["child"]["vars"]
    assert child["--ink"] == "#000000"
    assert child["--rule"] == "#abcdef"
    assert child["--paper"] == parchment["--paper"]


def test_extends_loops_and_unknowns_are_reported_not_fatal(tmp_path):
    source = tmp_path / "themes.json"
    source.write_text(json.dumps([
        {"id": "a", "extends": "b", "vars": {}},
        {"id": "b", "extends": "a", "vars": {}},
        {"id": "c", "extends": "nowhere", "vars": {"--ink": "#000000"}},
    ]), encoding="utf-8")
    themes = load(source, builtin=DEFAULT_THEMES)
    assert [t["id"] for t in themes] == ["a", "b", "c"]
    messages = [str(i) for i in check_themes(themes)]
    assert any("leads back to itself" in m for m in messages)
    assert any("'nowhere', which isn't a theme" in m for m in messages)


# ------------------------------------------------------------------- check


def _issues(tmp_path, theme, level=None):
    deck = read_deck(_deck(tmp_path, theme=theme))
    themes = load_themes()
    found = check_deck(deck, [t["id"] for t in themes], themes)
    found = [i for i in found if "deck theme" in i.where]
    return [i for i in found if level is None or i.level == level]


def test_a_good_deck_theme_has_no_issues(tmp_path):
    assert _issues(tmp_path, {"extends": "paper", "palette": PALETTE}) == []


def test_check_reports_unknown_extends_with_a_suggestion(tmp_path):
    (issue,) = _issues(tmp_path, {"extends": "parchmnt"}, "error")
    assert "isn't a theme" in issue.message and "parchment" in issue.hint


def test_check_reports_missing_fonts_and_bad_values(tmp_path):
    issues = _issues(tmp_path, {
        "palette": {**PALETTE, "accent": "orange"},
        "vars": {"card-bg": "#fff"},
        "fonts": [{"family": "Gone", "src": "fonts/gone.woff2"}, {"family": "NoSrc"}],
        "colour": "#fff",
    })
    text = " | ".join(i.message for i in issues)
    assert "font file not found: fonts/gone.woff2" in text
    assert "a font needs `family` and `src`" in text
    assert "palette accent 'orange' isn't a hex colour" in text
    assert "vars key 'card-bg' isn't a CSS custom property" in text
    assert "'colour' isn't a field" in text


def test_check_reports_low_contrast_in_a_deck_theme(tmp_path):
    issues = _issues(tmp_path, {"vars": {"--ink": "#cccccc", "--paper": "#dddddd"}})
    assert any("low contrast" in i.message for i in issues)


def test_check_flags_a_theme_that_changes_nothing(tmp_path):
    assert any("changes nothing" in i.message for i in _issues(tmp_path, {"name": "Empty"}))


def test_check_rejects_a_theme_of_the_wrong_type(tmp_path):
    deck = read_deck(_deck(tmp_path, theme=42))
    assert any("theme must be" in i.message for i in check_deck(deck, ["paper"], []))


# ------------------------------------------------------- build and server


def test_build_embeds_the_deck_theme_and_opens_in_it(tmp_path):
    deck = read_deck(_deck(tmp_path, theme={"palette": PALETTE}))
    html = build_deck(deck, tmp_path / "out").path.read_text(encoding="utf-8")
    assert 'const DECK_THEME = "deck:talk";' in html
    assert '"id": "deck:talk"' in html or '"id":"deck:talk"' in html


def test_server_offers_the_deck_theme_only_while_its_deck_is_open(tmp_path):
    _deck(tmp_path, theme={"palette": PALETTE, "name": "Q3"})
    _deck(tmp_path, name="other")
    client = TestClient(create_app(find_project(tmp_path), "talk"))

    assert client.get("/api/state").json()["theme"] == "deck:talk"
    themes = client.get("/api/themes").json()
    assert themes[0]["id"] == "deck:talk" and themes[0]["name"] == "Q3 (this deck)"
    assert "path" not in json.dumps(themes)  # no local paths leave the server
    assert "deck:talk" in client.get("/").text

    state = client.post("/api/deck", json={"id": "other"}).json()
    assert state["theme"] != "deck:talk"
    assert "deck:talk" not in [t["id"] for t in client.get("/api/themes").json()]
    # Asking for it while another deck is open changes nothing.
    assert client.post("/api/theme", json={"id": "deck:talk"}).json()["theme"] != "deck:talk"

    assert client.post("/api/deck", json={"id": "talk"}).json()["theme"] == "deck:talk"


def test_presenter_can_switch_away_and_back(tmp_path):
    _deck(tmp_path, theme={"palette": PALETTE})
    client = TestClient(create_app(find_project(tmp_path)))
    assert client.post("/api/theme", json={"id": "paper"}).json()["theme"] == "paper"
    assert client.post("/api/theme", json={"id": "deck:talk"}).json()["theme"] == "deck:talk"


def test_reload_picks_up_an_edited_deck_theme(tmp_path):
    path = _deck(tmp_path, theme={"palette": PALETTE})
    app = create_app(find_project(tmp_path))
    client = TestClient(app)
    data = json.loads(path.read_text())
    data["theme"]["vars"] = {"--paper": "#000000", "--ink": "#ffffff"}
    path.write_text(json.dumps(data), encoding="utf-8")
    app.state.reload_project()
    assert _vars(client.get("/api/themes").json(), "deck:talk")["--paper"] == "#000000"
    assert client.get("/api/state").json()["theme"] == "deck:talk"


def test_saved_deck_theme_survives_a_restart(tmp_path):
    _deck(tmp_path, theme={"palette": PALETTE})
    project = find_project(tmp_path)
    TestClient(create_app(project)).post("/api/theme", json={"id": "paper"})
    # The deck names its own theme, so a fresh start opens in it again.
    assert TestClient(create_app(project)).get("/api/state").json()["theme"] == "deck:talk"


# --------------------------------------------------------------------- cli


def test_themes_command_lists_deck_themes(tmp_path, monkeypatch, capsys):
    _deck(tmp_path, theme={"extends": "paper", "name": "Q3"})
    monkeypatch.chdir(tmp_path)
    assert main(["themes"]) == 0
    out = capsys.readouterr().out
    assert "deck:talk" in out and "Q3" in out and "extends paper" in out


def test_check_command_passes_a_valid_deck_theme(tmp_path, monkeypatch, capsys):
    _deck(tmp_path, theme={"extends": "paper", "palette": PALETTE})
    monkeypatch.chdir(tmp_path)
    assert main(["check", "-q"]) == 0
    assert main(["check", "-q", "--no-tips"]) == 0
    _deck(tmp_path, theme={"extends": "nope"})
    assert main(["check", "-q"]) == 1
    assert "isn't a theme" in capsys.readouterr().out


def test_schema_accepts_both_theme_forms():
    from glissade.project import SCHEMA_FILE

    schema = json.loads(Path(SCHEMA_FILE).read_text(encoding="utf-8"))
    forms = schema["$defs"]["deckObject"]["properties"]["theme"]["oneOf"]
    assert forms[0]["type"] == "string"
    assert forms[1]["$ref"] == "#/$defs/deckTheme"
    assert set(schema["$defs"]["deckTheme"]["properties"]) == {
        "name", "description", "extends", "palette", "vars", "fonts"}
