import pytest

from glissade.project import (
    ProjectNotFound,
    find_project,
    require_project,
    state_path_for,
)


def test_find_project_success(tmp_path):
    (tmp_path / "decks").mkdir()
    p = find_project(tmp_path)
    assert p is not None
    assert p.root == tmp_path
    assert p.decks_dir == tmp_path / "decks"

def test_find_project_subdirectory(tmp_path):
    (tmp_path / "decks").mkdir()
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    p = find_project(sub)
    assert p is not None
    assert p.root == tmp_path

def test_find_project_not_found(tmp_path):
    p = find_project(tmp_path)
    assert p is None
    with pytest.raises(ProjectNotFound):
        require_project(tmp_path)

def test_project_state_dir(tmp_path):
    (tmp_path / "decks").mkdir()
    p = find_project(tmp_path)
    state = p.state_dir
    assert state.name == ".glissade"
    sp = state_path_for(p)
    assert sp.name == "state.json"
    assert sp.parent == state

def test_project_config_defaults(tmp_path):
    (tmp_path / "decks").mkdir()
    p = find_project(tmp_path)
    cfg = p.config()
    assert isinstance(cfg, dict)
    assert "port" not in cfg or cfg["port"] is None or isinstance(cfg["port"], int)

def test_project_config_parsing(tmp_path):
    (tmp_path / "decks").mkdir()
    toml_content = 'deck = "demo"\nport = 8080\nhost = "127.0.0.1"\nopen = true\n'
    (tmp_path / "glissade.toml").write_text(toml_content, encoding="utf-8")
    p = find_project(tmp_path)
    cfg = p.config()
    assert cfg.get("deck") == "demo"
    assert cfg.get("port") == 8080
    assert cfg.get("host") == "127.0.0.1"
    assert cfg.get("open") is True
