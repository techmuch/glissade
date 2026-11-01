from glissade.cli import main
from glissade.project import Project
from glissade.scaffold import apply, plan


def _init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    return Project(tmp_path)


def _actions(project):
    return {c.name: c.action for c in plan(project)}


def test_fresh_project_is_current(tmp_path, monkeypatch):
    project = _init(tmp_path, monkeypatch)
    assert set(_actions(project).values()) == {"current"}


def test_untouched_stale_file_is_updated_in_place(tmp_path, monkeypatch):
    project = _init(tmp_path, monkeypatch)
    agents = tmp_path / "AGENTS.md"
    agents.write_text("from an older release\n", encoding="utf-8")
    # Pretend that older text is what Glissade last wrote.
    from glissade.scaffold import _hash, write_manifest
    write_manifest(project, {"AGENTS.md": _hash(agents)})

    assert _actions(project)["AGENTS.md"] == "update"
    apply(project, plan(project))
    assert not (tmp_path / "AGENTS.md.bak").exists()
    assert _actions(project)["AGENTS.md"] == "current"


def test_user_edits_are_backed_up_or_kept(tmp_path, monkeypatch):
    project = _init(tmp_path, monkeypatch)
    agents = tmp_path / "AGENTS.md"
    agents.write_text("my own house rules\n", encoding="utf-8")
    assert _actions(project)["AGENTS.md"] == "edited"

    apply(project, plan(project), keep_edits=True)
    assert agents.read_text(encoding="utf-8") == "my own house rules\n"

    apply(project, plan(project))
    assert (tmp_path / "AGENTS.md.bak").read_text(encoding="utf-8") == "my own house rules\n"
    assert _actions(project)["AGENTS.md"] == "current"


def test_update_never_touches_decks(tmp_path, monkeypatch):
    project = _init(tmp_path, monkeypatch)
    deck = tmp_path / "decks" / "welcome.json"
    deck.write_text('{"slides": []}', encoding="utf-8")
    (tmp_path / "AGENTS.md").unlink()
    apply(project, plan(project))
    assert deck.read_text(encoding="utf-8") == '{"slides": []}'
    assert (tmp_path / "AGENTS.md").exists()
