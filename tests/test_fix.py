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


def test_plan_finds_youtube_links_in_quads():
    data = {"format": 1, "slides": [{
        "layout": "quad-chart",
        "quads": [
            {"media": {"src": "https://www.youtube.com/watch?v=abcdefgh"}},
            {"body": "b"}, {"body": "c"}, {"body": "d"},
        ],
    }]}
    fixes = plan(data)
    assert [(f.where, f.after) for f in fixes] == [
        ("slide 1 quad 1", "https://www.youtube.com/embed/abcdefgh")
    ]


def test_plan_does_not_modify_the_deck():
    data = {"slides": [{"layout": "media-rite"}]}
    plan(data)
    assert data == {"slides": [{"layout": "media-rite"}]}


def test_apply_changes_exactly_what_plan_reports(tmp_path):
    deck = {"slides": [
        {"layout": "media-rite", "cls": "asks",
         "media": {"src": "https://youtu.be/abcdefgh"}},
        {"layout": "quad-chart", "quads": [
            {"media": {"src": "https://www.youtube.com/watch?v=zyxwvuts"}}, {}, {}, {}]},
    ]}
    path = tmp_path / "deck.json"
    path.write_text(json.dumps(deck), encoding="utf-8")
    planned = [str(f) for f in plan(json.loads(path.read_text()))]
    applied = [str(f) for f in apply(path)]
    assert planned == applied
    after = json.loads(path.read_text())
    assert plan(after) == []
    assert after["slides"][0]["cls"] == "ask"
    assert after["slides"][1]["quads"][0]["media"]["src"].endswith("/embed/zyxwvuts")


def test_second_fix_keeps_the_original_backup(tmp_path):
    path = tmp_path / "deck.json"
    original = json.dumps({"slides": [{"layout": "media-rite"}]})
    path.write_text(original, encoding="utf-8")
    apply(path)
    data = json.loads(path.read_text())
    data["slides"][0]["layout"] = "titel"
    path.write_text(json.dumps(data), encoding="utf-8")
    apply(path)
    assert (tmp_path / "deck.json.bak").read_text(encoding="utf-8") == original
