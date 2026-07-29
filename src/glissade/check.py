"""Validate a deck before you stand in front of a room with it.

`schema.json` ships alongside for editor autocomplete, but this is a
purpose-built checker rather than a generic schema validator, because the
useful errors are the ones a schema can't express: a media file that isn't
there, a layout whose name is a near-miss, a grid with one image in it.

An AI harness authoring decks is expected to run `glissade check` and fix what
it reports before handing the deck over.
"""

from __future__ import annotations

import difflib
import functools
import json
from pathlib import Path
from typing import Any

from . import __version__
from .project import SCHEMA_FILE


@functools.lru_cache(maxsize=1)
def _schema() -> dict:
    """The shipped schema, read once.

    Field names and layouts come from here rather than being repeated, so the
    checker and the schema cannot disagree about what a deck may contain.
    """
    try:
        with SCHEMA_FILE.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):  # pragma: no cover - shipped with the wheel
        return {}


def _known(defn: str) -> set:
    return set(_schema().get("$defs", {}).get(defn, {}).get("properties") or {})


LAYOUTS = set(
    _schema().get("$defs", {}).get("slide", {}).get("properties", {})
    .get("layout", {}).get("enum")
    or [
        "title", "title-content", "section", "title-only", "two-content",
        "comparison", "content-caption", "picture-caption", "media-right",
        "media-left", "media-full", "media-caption", "grid", "quad-chart", "blank",
    ]
)
MODIFIERS = {"ask", "story", "center"}

# Which layouts actually render a media region. Putting an image on a layout
# that has nowhere to draw it is silent data loss, so it's worth saying.
MEDIA_LAYOUTS = {
    "two-content", "comparison", "content-caption", "picture-caption",
    "media-right", "media-left", "media-full", "media-caption", "grid",
    "quad-chart",
}
TEXT_ONLY = {"title", "title-only", "section", "title-content"}


class Issue:
    def __init__(self, level: str, where: str, message: str, hint: str = ""):
        self.level = level          # "error" | "warning"
        self.where = where
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        line = f"{self.where}: {self.message}"
        return f"{line}\n      {self.hint}" if self.hint else line


def _did_you_mean(value: str, options) -> str:
    close = difflib.get_close_matches(value, sorted(options), n=1, cutoff=0.6)
    return f"Did you mean {close[0]!r}?" if close else ""


def _unknown_fields(node: Any, defn: str, where: str, out: list) -> None:
    """Flag fields this version doesn't understand.

    They are otherwise silent: an unrecognised slide field rides along in the
    data and renders nothing, so a deck written for a newer Glissade would
    lose content without saying a word.
    """
    known = _known(defn)
    if not isinstance(node, dict) or not known:
        return
    for key in node:
        if key in known or key.startswith("_"):
            continue
        hint = _did_you_mean(key, known)
        out.append(Issue(
            "warning", where,
            f"{key!r} isn't a field Glissade {__version__} understands — it will be ignored",
            hint or "If the deck was written for a newer release, run `glissade upgrade`.",
        ))


def _check_media(node: Any, where: str, base: Path, out: list[Issue]) -> None:
    if not isinstance(node, dict):
        out.append(Issue("error", where, "media must be an object"))
        return
    kinds = [k for k in ("file", "srcdoc", "src") if node.get(k)]
    if not kinds:
        out.append(Issue("error", where, "media has no file, srcdoc or src"))
        return
    if len(kinds) > 1:
        out.append(Issue(
            "warning", where,
            f"media sets {' and '.join(kinds)}; only {kinds[0]!r} is used",
        ))
    if node.get("file"):
        path = base / str(node["file"])
        if not path.is_file():
            out.append(Issue("error", where, f"activity file not found: {node['file']}"))
        elif path.suffix.lower() not in (".html", ".htm"):
            out.append(Issue("warning", where, f"activity is not HTML: {node['file']}"))
    src = node.get("src")
    if src:
        if not str(src).startswith(("http://", "https://")):
            out.append(Issue("error", where, f"media src is not a URL: {src}"))
        else:
            out.append(Issue("warning", where, f"needs live internet: {src}"))
            if "youtube.com/watch" in src or "youtu.be/" in src:
                out.append(Issue(
                    "error", where, "YouTube watch link will not embed",
                    "Use the /embed/ form: https://www.youtube.com/embed/VIDEO_ID",
                ))


def _check_image(node: Any, where: str, base: Path, out: list[Issue]) -> None:
    if not isinstance(node, dict):
        out.append(Issue("error", where, "image must be an object"))
        return
    src = node.get("src")
    if not src:
        out.append(Issue("error", where, "image has no src"))
        return
    if str(src).startswith(("http://", "https://")):
        out.append(Issue(
            "warning", where, f"remote image needs the network: {src}",
            "Download it beside the deck so it embeds into the build.",
        ))
        return
    if str(src).startswith("data:"):
        return
    if not (base / str(src)).is_file():
        out.append(Issue("error", where, f"image not found: {src}"))
    if node.get("fit") and node["fit"] not in ("contain", "cover"):
        out.append(Issue(
            "warning",
            where,
            f"fit should be 'contain' or 'cover', got {node['fit']!r}",
        ))


def check_slides(slides: list[Any], base: Path, label: str = "") -> list[Issue]:
    out: list[Issue] = []
    prefix = f"{label} " if label else ""

    if not isinstance(slides, list):
        return [Issue("error", prefix.strip() or "deck", "slides must be an array")]
    if not slides:
        return [Issue("error", prefix.strip() or "deck", "deck has no slides")]

    for idx, slide in enumerate(slides, start=1):
        where = f"{prefix}slide {idx}"
        if not isinstance(slide, dict):
            out.append(Issue("error", where, "slide must be an object"))
            continue

        layout = slide.get("layout", "blank")
        known = layout in LAYOUTS
        if not known:
            out.append(Issue(
                "error", where, f"unknown layout {layout!r}", _did_you_mean(layout, LAYOUTS)
            ))
            # Don't cascade: an unknown layout would otherwise also trip the
            # blank-needs-html check, and one mistake should report once.
            layout = None

        for word in str(slide.get("cls", "")).split():
            if word not in MODIFIERS:
                out.append(Issue(
                    "warning", where, f"unknown cls modifier {word!r}",
                    _did_you_mean(word, MODIFIERS),
                ))

        if layout == "blank":
            if not slide.get("html"):
                out.append(Issue(
                    "error", where, "blank layout with no html",
                    "Either add `html`, or pick a layout and use its fields.",
                ))
        elif known and slide.get("html"):
            out.append(Issue(
                "warning", where,
                f"html is ignored on the {layout!r} layout",
            ))

        # Something has to render.
        visible = any(slide.get(k) for k in (
            "heading", "subheading", "body", "bullets", "quote", "caption",
            "image", "media", "images", "left", "right", "quads", "html", "eyebrow",
        ))
        if not visible:
            out.append(Issue("error", where, "slide has no visible content"))

        _unknown_fields(slide, "slide", where, out)
        if slide.get("image"):
            _check_image(slide["image"], where, base, out)
            _unknown_fields(slide["image"], "image", f"{where} image", out)
        if slide.get("media"):
            _check_media(slide["media"], where, base, out)
            _unknown_fields(slide["media"], "media", f"{where} media", out)
        for side in ("left", "right"):
            if isinstance(slide.get(side), dict):
                _unknown_fields(slide[side], "block", f"{where} {side}", out)

        images = slide.get("images")
        if images is not None:
            if known and layout != "grid":
                out.append(Issue(
                    "warning",
                    where,
                    f"`images` only renders on the grid layout, not {layout!r}",
                ))
            if not isinstance(images, list) or not 2 <= len(images) <= 4:
                count = len(images) if isinstance(images, list) else "?"
                out.append(Issue(
                    "error",
                    where,
                    f"grid needs two to four images, got {count}",
                ))
            else:
                for i, img in enumerate(images, start=1):
                    _check_image(img, f"{where} image {i}", base, out)
        elif layout == "grid":
            out.append(Issue("error", where, "grid layout with no `images`"))

        for side in ("left", "right"):
            block = slide.get(side)
            if block is None:
                continue
            if known and layout not in ("two-content", "comparison"):
                out.append(Issue(
                    "warning", where,
                    f"`{side}` only renders on two-content and comparison, not {layout!r}",
                ))
            if isinstance(block, dict):
                if block.get("image"):
                    _check_image(block["image"], f"{where} {side}", base, out)
                if block.get("media"):
                    _check_media(block["media"], f"{where} {side}", base, out)
        if layout in ("two-content", "comparison") and not (
            slide.get("left") or slide.get("right")
        ):
            out.append(Issue("error", where, f"{layout} needs `left` and `right`"))

        quads = slide.get("quads")
        if quads is not None:
            if known and layout != "quad-chart":
                out.append(Issue(
                    "warning",
                    where,
                    f"`quads` only renders on the quad-chart layout, not {layout!r}",
                ))
            if not isinstance(quads, list) or len(quads) != 4:
                out.append(Issue("error", where, "quad-chart needs exactly four `quads`"))
            else:
                for q_idx, quad in enumerate(quads, start=1):
                    q_where = f"{where} quad {q_idx}"
                    if not isinstance(quad, dict):
                        out.append(Issue("error", q_where, "quad must be an object"))
                        continue
                    _unknown_fields(quad, "quad", q_where, out)
                    if quad.get("image"):
                        _check_image(quad["image"], q_where, base, out)
                    if quad.get("media"):
                        _check_media(quad["media"], q_where, base, out)
                    q_visible = any(
                        quad.get(k)
                        for k in ("subheading", "body", "bullets", "image", "media")
                    )
                    if not q_visible:
                        out.append(Issue("error", q_where, "quad has no visible content"))
        elif layout == "quad-chart":
            out.append(Issue("error", where, "quad-chart layout with no `quads`"))

        if layout in TEXT_ONLY and (slide.get("image") or slide.get("media")):
            out.append(Issue(
                "warning", where,
                f"the {layout!r} layout has no media region, so it will not be shown",
                "Use media-right, media-full, or picture-caption instead.",
            ))

        if not slide.get("notes"):
            out.append(Issue("warning", where, "no speaker notes"))

        aspect = slide.get("aspect")
        if aspect and aspect not in ("auto", "fill"):
            text = str(aspect)
            parts = text.replace("/", ":").replace("x", ":").split(":")
            ok = len(parts) == 2 and all(p.strip().replace(".", "", 1).isdigit() for p in parts)
            if not ok and not text.replace(".", "", 1).isdigit():
                out.append(Issue(
                    "error", where, f"aspect {aspect!r} is not a ratio",
                    "Use '16:9', '4:3', a number, or 'auto'.",
                ))

    return out


def check_requirement(deck: dict[str, Any], label: str = "") -> list[Issue]:
    """Honour a deck's declared minimum version."""
    from .upgrade import BadRequirement, satisfies

    requirement = deck.get("requires")
    if not requirement:
        return []
    where = f"{label}deck" if label else "deck"
    try:
        ok = satisfies(__version__, str(requirement))
    except BadRequirement as exc:
        return [Issue("error", where, f"can't read the `glissade` requirement: {exc}",
                      'Use something like ">=0.6".')]
    if ok:
        return []
    return [Issue(
        "error", where,
        f"needs Glissade {requirement}, but this is {__version__}",
        "Run `glissade upgrade`. Presenting anyway will silently skip anything "
        "this release doesn't understand.",
    )]


def check_deck(deck: dict[str, Any]) -> list[Issue]:
    """Validate one loaded deck. Media paths resolve beside the deck file."""
    base = Path(deck["path"]).resolve().parent
    label = f"[{deck['id']}] "
    issues = check_requirement(deck, label)
    issues += _deck_level(deck, label)
    return issues + check_slides(deck.get("slides", []), base, label=f"[{deck['id']}]")


def _deck_level(deck: dict[str, Any], label: str) -> list[Issue]:
    out: list[Issue] = []
    raw = deck.get("raw")
    if isinstance(raw, dict):
        _unknown_fields(raw, "deckObject", f"{label}deck", out)
    return out
