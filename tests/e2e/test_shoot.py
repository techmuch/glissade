"""`glissade shoot`: screenshots plus rendered-layout measurements."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from glissade.app import load_themes
from glissade.decks import read_deck
from glissade.shoot import shoot_deck

pytestmark = pytest.mark.e2e


def _deck(tmp_path: Path, slides: list[dict]) -> dict:
    path = tmp_path / "decks" / "talk.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"title": "T", "slides": slides}), encoding="utf-8")
    return read_deck(path)


def test_shoot_writes_pngs_and_reports_real_problems_only(tmp_path: Path):
    slides = [
        {
            "layout": "cards", "numbered": True, "eyebrow": "How", "heading": "Keys",
            "cards": [
                {"title": "One", "body": "A sentence.", "source": "Ref 1"},
                {"title": "Two", "body": "A sentence."},
                {"title": "Three", "body": "A sentence."},
            ],
            "notes": "n",
        },
        {
            "layout": "quote", "eyebrow": "Why", "heading": "Quoted",
            "quote": "A quotation long enough to wrap onto a second line of the panel.",
            "cite": "Someone", "subheading": "Pair it", "body": "<p>With this.</p>",
            "notes": "n",
        },
        {
            "layout": "title-content", "eyebrow": "Too much", "heading": "Overflowing",
            "bullets": [f"Point {i} with enough words to take a line" for i in range(30)],
            "notes": "n",
        },
    ]
    shots = shoot_deck(_deck(tmp_path, slides), tmp_path / "shots", load_themes())

    assert [s.path.name for s in shots] == ["slide-01.png", "slide-02.png", "slide-03.png"]
    assert all(s.path.stat().st_size > 1000 for s in shots)

    # Cards and the quote are sized by their children; no small-text alarms.
    assert not any("small for a room" in p for p in shots[0].problems + shots[1].problems)
    # Thirty bullets cannot fit.
    assert any("overflows" in p for p in shots[2].problems)


def test_shoot_selects_slides(tmp_path: Path):
    slides = [{"layout": "title", "heading": f"S{i}", "notes": "n"} for i in range(4)]
    shots = shoot_deck(_deck(tmp_path, slides), tmp_path / "shots", load_themes(), slides="2,4")
    assert [s.n for s in shots] == [2, 4]
