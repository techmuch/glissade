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

from .assets import media_nodes
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
    return _fixes(data, write=False)[0]


def _with_format(data: dict) -> dict:
    """The deck with a format stamp, placed with the other metadata in the
    order the schema declares it: after $schema and glissade, before the
    human-facing title."""
    rebuilt: dict = {}
    placed = False
    for key, value in data.items():
        if not placed and key not in ("$schema", "glissade"):
            rebuilt["format"] = CURRENT_FORMAT
            placed = True
        rebuilt[key] = value
    if not placed:
        rebuilt["format"] = CURRENT_FORMAT
    return rebuilt


def _fixes(data: Any, write: bool) -> tuple[list[Fix], Any]:
    """Find every fix and, when `write` is set, make it in place.

    Planning and applying are one walk, so what `check --fix` reports and
    what it changes can never disagree. Returns the fixes and the (possibly
    rebuilt) deck.
    """
    fixes: list[Fix] = []
    slides = data.get("slides", []) if isinstance(data, dict) else data
    if not isinstance(slides, list):
        return fixes, data

    if isinstance(data, dict) and "format" not in data:
        fixes.append(Fix("deck", "absent", str(CURRENT_FORMAT), "record the deck format"))
        if write:
            data = _with_format(data)

    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            continue
        where = f"slide {index}"

        layout = slide.get("layout")
        if isinstance(layout, str) and layout not in LAYOUTS:
            better = _confident(layout, LAYOUTS)
            if better:
                fixes.append(Fix(where, layout, better, "correct the layout name"))
                if write:
                    slide["layout"] = better

        cls = slide.get("cls")
        if isinstance(cls, str):
            words = cls.split()
            fixed = [w if w in MODIFIERS else (_confident(w, MODIFIERS) or w) for w in words]
            if fixed != words:
                fixes.append(Fix(where, cls, " ".join(fixed), "correct a cls modifier"))
                if write:
                    slide["cls"] = " ".join(fixed)

        for kind, label, node in media_nodes(slide):
            src = node.get("src")
            if kind != "media" or not isinstance(src, str):
                continue
            better = embed_url(src)
            if better:
                fixes.append(Fix(f"{where}{label}", src, better, "use the YouTube embed URL"))
                if write:
                    node["src"] = better
    return fixes, data


def apply(path: Path, backup: bool = True) -> list[Fix]:
    """Apply every available fix to a deck file. Returns what was changed.

    The original is copied to `<name>.bak` first: this rewrites a file the
    user wrote, and reformatting alone is reason enough to keep a copy. An
    existing backup is left alone, so running --fix twice still leaves the
    file as it was before Glissade first touched it.
    """
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    fixes, data = _fixes(data, write=True)
    if not fixes:
        return []

    bak = path.with_suffix(path.suffix + ".bak")
    if backup and not bak.exists():
        shutil.copyfile(path, bak)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return fixes
