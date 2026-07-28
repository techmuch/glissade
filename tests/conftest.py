import json

import pytest


@pytest.fixture
def sample_deck_data():
    return {
        "title": "Test Presentation",
        "format": 1,
        "glissade": ">=0.6",
        "slides": [
            {
                "title": "Welcome Slide",
                "layout": "title",
                "heading": "Welcome to Glissade",
                "body": "<p>A presentation deck tool.</p>",
                "notes": "Introduce the presentation."
            },
            {
                "title": "Content Slide",
                "layout": "media-right",
                "eyebrow": "Features",
                "heading": "Self-contained decks",
                "body": "<p>Works offline anywhere.</p>",
                "notes": "Highlight offline functionality."
            }
        ]
    }

@pytest.fixture
def sample_deck_file(tmp_path, sample_deck_data):
    decks_dir = tmp_path / "decks"
    decks_dir.mkdir(parents=True, exist_ok=True)
    deck_path = decks_dir / "talk.json"
    deck_path.write_text(json.dumps(sample_deck_data, indent=2), encoding="utf-8")
    return deck_path
