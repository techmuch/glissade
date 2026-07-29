from glissade.build import build_all, build_deck
from glissade.project import require_project


def test_build_deck(tmp_path, sample_deck_file):
    deck = {
        "id": "talk",
        "title": "Test Deck",
        "path": str(sample_deck_file),
        "slides": [
            {
                "layout": "title",
                "heading": "Built Deck",
                "notes": "Notes"
            }
        ]
    }
    out_dir = tmp_path / "build"
    result = build_deck(deck, out_dir)
    assert result.path.exists()
    assert result.path.name == "talk.html"
    assert result.size > 0

    content = result.path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "Built Deck" in content

def test_build_all(tmp_path, sample_deck_file):
    project = require_project(tmp_path)
    deck = {
        "id": "talk",
        "title": "Test Deck",
        "path": str(sample_deck_file),
        "slides": [
            {
                "layout": "title",
                "heading": "Built Deck",
                "notes": "Notes"
            }
        ]
    }
    results = build_all(project, [deck])
    assert len(results) == 1
    assert results[0].path.exists()
