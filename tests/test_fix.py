import json

from glissade.fix import apply, embed_url, plan


def test_embed_url_conversion():
    assert embed_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "https://www.youtube.com/embed/dQw4w9WgXcQ"
    assert embed_url("https://youtu.be/dQw4w9WgXcQ") == "https://www.youtube.com/embed/dQw4w9WgXcQ"
    assert embed_url("https://www.youtube.com/embed/dQw4w9WgXcQ") is None
    assert embed_url("https://example.com/video.mp4") is None

def test_plan_fixes():
    data = {
        "title": "Test",
        "slides": [
            {
                "layout": "media-rite",
                "media": {"src": "https://www.youtube.com/watch?v=abc1234"}
            }
        ]
    }
    fixes = plan(data)
    assert len(fixes) == 3  # format stamp missing, layout typo, YouTube URL
    descriptions = [f.what for f in fixes]
    assert "record the deck format" in descriptions
    assert "correct the layout name" in descriptions
    assert "use the YouTube embed URL" in descriptions

def test_apply_fixes(tmp_path):
    deck_path = tmp_path / "deck.json"
    initial_data = {
        "title": "Test Deck",
        "slides": [
            {
                "layout": "media-rite",
                "notes": "Test notes"
            }
        ]
    }
    deck_path.write_text(json.dumps(initial_data, indent=2), encoding="utf-8")

    fixes = apply(deck_path, backup=True)
    assert len(fixes) >= 1
    assert (tmp_path / "deck.json.bak").exists()

    updated = json.loads(deck_path.read_text(encoding="utf-8"))
    assert updated.get("format") == 1
    assert updated["slides"][0]["layout"] == "media-right"
