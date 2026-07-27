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

from . import DECKS_DIR


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
        "path": path,
        "slides": slides,
    }


def discover(directory: Path | None = None) -> list[dict[str, Any]]:
    """Every deck in the decks directory, ordered by an optional `order` key
    then by title, so the picker is stable between runs."""
    d = directory or DECKS_DIR
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
