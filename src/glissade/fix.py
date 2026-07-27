"""Corrections `check` can apply for you.

Deliberately narrow. A deck is your writing, and a tool that rewrites your
source on a guess is worse than one that tells you what's wrong. So only
changes with a single obviously-correct answer are made here:

  * a YouTube watch link rewritten to the /embed/ form it must have
  * a layout or modifier that is unmistakably a typo for a real one
  * the format stamp, when missing

Notably absent: renaming unrecognised *fields*. The nearest match is often
wrong — `subtitle` is closer to `subheading` in meaning but closer to `title`
by spelling — and a field this release doesn't know may simply belong to a
newer one. Those stay reported, never rewritten.
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .check import LAYOUTS, MODIFIERS

CURRENT_FORMAT = 1

# Only rewrite a name when the match is barely a question. `check` suggests at
# 0.6 to be helpful; editing someone's file deserves a higher bar.
RENAME_CONFIDENCE = 0.82

_YT_WATCH = re.compile(r"[?&]v=([A-Za-z0-9_-]{6,})")
_YT_SHORT = re.compile(r"youtu\.be/([A-Za-z0-9_-]{6,})")


@dataclass
class Fix:
    where: str
    before: str
    after: str
    what: str

    def __str__(self) -> str:
        return f"{self.where}: {self.what}  {self.before!r} -> {self.after!r}"


def _confident(value: str, options) -> str | None:
    match = difflib.get_close_matches(value, sorted(options), n=1, cutoff=RENAME_CONFIDENCE)
    return match[0] if match else None


def embed_url(src: str) -> str | None:
    """Turn a YouTube watch link into the embed form, or None if it isn't one."""
    if "youtube.com/embed/" in src:
        return None
    vid = None
    if "youtube.com" in src and "/watch" in src:
        m = _YT_WATCH.search(src)
        vid = m.group(1) if m else None
    else:
        m = _YT_SHORT.search(src)
        vid = m.group(1) if m else None
    return f"https://www.youtube.com/embed/{vid}" if vid else None


def plan(data: Any) -> list[Fix]:
    """Everything that can be corrected in this deck, without doing it."""
    fixes: list[Fix] = []
    slides = data.get("slides", []) if isinstance(data, dict) else data
    if not isinstance(slides, list):
        return fixes

    if isinstance(data, dict) and "format" not in data:
        fixes.append(Fix("deck", "absent", str(CURRENT_FORMAT), "record the deck format"))

    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            continue
        where = f"slide {index}"

        layout = slide.get("layout")
        if isinstance(layout, str) and layout not in LAYOUTS:
            better = _confident(layout, LAYOUTS)
            if better:
                fixes.append(Fix(where, layout, better, "correct the layout name"))

        cls = slide.get("cls")
        if isinstance(cls, str):
            words = cls.split()
            fixed = [
                _confident(w, MODIFIERS) or w if w not in MODIFIERS else w for w in words
            ]
            if fixed != words:
                fixes.append(Fix(where, cls, " ".join(fixed), "correct a cls modifier"))

        for node, label in _media_nodes(slide):
            src = node.get("src")
            if isinstance(src, str):
                better = embed_url(src)
                if better:
                    fixes.append(Fix(f"{where}{label}", src, better,
                                     "use the YouTube embed URL"))
    return fixes


def _media_nodes(slide: dict):
    if isinstance(slide.get("media"), dict):
        yield slide["media"], ""
    for side in ("left", "right"):
        block = slide.get(side)
        if isinstance(block, dict) and isinstance(block.get("media"), dict):
            yield block["media"], f" {side}"


def apply(path: Path, backup: bool = True) -> list[Fix]:
    """Apply every available fix to a deck file. Returns what was changed.

    The original is copied to `<name>.bak` first: this rewrites a file the
    user wrote, and reformatting alone is reason enough to keep a copy.
    """
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    fixes = plan(data)
    if not fixes:
        return []

    slides = data.get("slides", []) if isinstance(data, dict) else data

    if isinstance(data, dict) and "format" not in data:
        # Placed with the other metadata, in the order the schema declares it:
        # after $schema and glissade, before the human-facing title.
        rebuilt = {}
        placed = False
        for key, value in data.items():
            if not placed and key not in ("$schema", "glissade"):
                rebuilt["format"] = CURRENT_FORMAT
                placed = True
            rebuilt[key] = value
        if not placed:
            rebuilt["format"] = CURRENT_FORMAT
        data = rebuilt
        slides = data.get("slides", [])

    for slide in slides:
        if not isinstance(slide, dict):
            continue
        layout = slide.get("layout")
        if isinstance(layout, str) and layout not in LAYOUTS:
            better = _confident(layout, LAYOUTS)
            if better:
                slide["layout"] = better
        cls = slide.get("cls")
        if isinstance(cls, str):
            words = cls.split()
            fixed = [
                _confident(w, MODIFIERS) or w if w not in MODIFIERS else w for w in words
            ]
            if fixed != words:
                slide["cls"] = " ".join(fixed)
        for node, _ in _media_nodes(slide):
            src = node.get("src")
            if isinstance(src, str):
                better = embed_url(src)
                if better:
                    node["src"] = better

    if backup:
        shutil.copyfile(path, path.with_suffix(path.suffix + ".bak"))
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return fixes
