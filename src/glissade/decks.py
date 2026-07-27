"""Deck discovery.

Any .json file in `decks/` is a presentation. Two shapes are accepted:

    [ {...slide...}, {...} ]                    a bare list of slides
    { "title": "...", "slides": [ ... ] }       with metadata

The second form lets a deck name itself, which is what the browser tab, the
startup banner, and the remote's deck picker all show.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .project import Project


def _title_from(stem: str) -> str:
    return stem.replace("-", " ").replace("_", " ").strip().title()


def read_deck(path: Path) -> dict[str, Any]:
    """Load one deck file into a normal shape: id, title, subtitle, slides."""
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, list):
        meta: dict[str, Any] = {}
        slides = data
    elif isinstance(data, dict):
        meta = data
        slides = data.get("slides") or []
    else:
        raise ValueError(f"{path.name}: expected a list of slides or an object")

    return {
        "id": path.stem,
        "title": meta.get("title") or _title_from(path.stem),
        "subtitle": meta.get("subtitle", ""),
        # The version this deck says it needs, if it says.
        "requires": meta.get("glissade", ""),
        # The deck object as written, so `check` can see fields this release
        # doesn't know about instead of silently dropping them.
        "raw": meta if isinstance(data, dict) else {},
        "path": path,
        "slides": [_normalise(slide, i) for i, slide in enumerate(slides, start=1)],
    }


def _normalise(slide: Any, index: int) -> Any:
    """Fill in the fields the UI needs but authors shouldn't have to write.

    `n` and `title` are documented as optional, and the remote's jump list
    keys off both — so a deck that omits them must still be navigable. Order
    always comes from array position, never from a hand-written `n`.
    """
    if not isinstance(slide, dict):
        return slide
    slide = dict(slide)
    slide["n"] = index
    if not slide.get("title"):
        slide["title"] = _label_for(slide, index)
    return slide


def _label_for(slide: dict, index: int) -> str:
    """A jump-list label derived from whatever the slide actually says."""
    import re

    for key in ("heading", "subheading", "eyebrow", "caption", "body", "html"):
        raw = slide.get(key)
        if isinstance(raw, str) and raw.strip():
            text = re.sub(r"<[^>]+>", " ", raw)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                return text[:57].rstrip() + "…" if len(text) > 58 else text
    return f"Slide {index}"


def discover(directory: Path | Project) -> list[dict[str, Any]]:
    """Every deck in a directory, ordered by an optional `order` key then by
    title, so the picker is stable between runs."""
    d = directory.decks_dir if isinstance(directory, Project) else Path(directory)
    out = []
    if not d.is_dir():
        return out
    for path in sorted(d.glob("*.json")):
        try:
            deck = read_deck(path)
        except (OSError, ValueError) as exc:
            print(f"  ! skipping {path.name}: {exc}")
            continue
        try:
            with path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
            deck["order"] = raw.get("order", 100) if isinstance(raw, dict) else 100
        except (OSError, ValueError):
            deck["order"] = 100
        out.append(deck)
    out.sort(key=lambda d: (d.get("order", 100), d["title"]))
    return out


def resolve(name: str | None, decks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find a deck by id, by title, or by path. Falls back to the first deck."""
    if not decks:
        return None
    if not name:
        return decks[0]

    for deck in decks:
        if name in (deck["id"], deck["title"]):
            return deck

    # Also accept a path to a file outside decks/, so one-off decks still work.
    path = Path(name)
    if path.suffix == ".json" and path.is_file():
        try:
            return read_deck(path.resolve())
        except (OSError, ValueError):
            return decks[0]
    return decks[0]


def summaries(decks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Just what the remote needs to draw the picker — no slide payloads."""
    return [
        {
            "id": d["id"],
            "title": d["title"],
            "subtitle": d.get("subtitle", ""),
            "count": len(d["slides"]),
        }
        for d in decks
    ]
