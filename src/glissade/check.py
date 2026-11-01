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
import re
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
        "media-left", "media-full", "media-caption", "grid", "quad-chart",
        "cards", "quote", "blank",
    ]
)
MODIFIERS = {"ask", "story", "center"}

# Which layouts actually render a media region. Putting an image on a layout
# that has nowhere to draw it is silent data loss, so it's worth saying.
MEDIA_LAYOUTS = {
    "two-content", "comparison", "content-caption", "picture-caption",
    "media-right", "media-left", "media-full", "media-caption", "grid",
    "quad-chart", "quote",
}
TEXT_ONLY = {"title", "title-only", "section", "title-content", "cards"}

# Layouts that draw a `callout`. On the others it would vanish silently.
CALLOUT_LAYOUTS = {
    "title-content", "two-content", "comparison", "content-caption",
    "media-right", "media-left", "quad-chart", "cards", "quote",
}

# Design guidance. These are judgement calls, so they are tips rather than
# warnings: a deck can ignore every one of them and still present.
MAX_BODY_WORDS = 40
MAX_BULLETS = 6
MAX_HEADING_CHARS = 70
MAX_CALLOUT_WORDS = 30
MAX_CARD_WORDS = 30
MAX_SLIDE_WORDS = 90

_FOCUS = re.compile(
    r"^((left|center|right|top|bottom|\d{1,3}(\.\d+)?%)(\s+|$)){1,2}$", re.IGNORECASE
)
_TAG = re.compile(r"<[^>]+>")


def _words(html: Any) -> int:
    if not isinstance(html, str):
        return 0
    return len(_TAG.sub(" ", html).split())


class Issue:
    def __init__(self, level: str, where: str, message: str, hint: str = ""):
        self.level = level          # "error" | "warning" | "tip"
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
    elif not str(src).startswith("data:") and not (base / str(src)).is_file():
        out.append(Issue("error", where, f"image not found: {src}"))
    # Alt text and fit matter wherever the pixels come from.
    _check_image_details(node, where, out)


def _check_image_details(node: dict, where: str, out: list[Issue]) -> None:
    if node.get("fit") and node["fit"] not in ("contain", "cover"):
        out.append(Issue(
            "warning",
            where,
            f"fit should be 'contain' or 'cover', got {node['fit']!r}",
        ))
    if "alt" not in node:
        out.append(Issue(
            "warning", where, "image has no alt text",
            'Describe what it shows for people who can\'t see it, or use "alt": "" '
            "if it is purely decorative.",
        ))
    focus = node.get("focus")
    if focus is not None and not (isinstance(focus, str) and _FOCUS.match(focus.strip())):
        out.append(Issue(
            "warning", where, f"focus {focus!r} isn't a position Glissade understands",
            "Use keywords or percentages: 'center top', 'right', '70% 30%'.",
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
            "cards", "callout",
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

        _check_blocks(slide, layout, known, where, base, out)
        _design_tips(slide, layout, where, out)

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


def _check_blocks(
    slide: dict, layout: str | None, known: bool, where: str, base: Path, out: list[Issue]
) -> None:
    """cards, callout, quote, scrim and source: the design building blocks."""
    cards = slide.get("cards")
    if cards is not None:
        if known and layout != "cards":
            out.append(Issue(
                "warning", where, f"`cards` only renders on the cards layout, not {layout!r}",
            ))
        if not isinstance(cards, list) or not 2 <= len(cards) <= 4:
            count = len(cards) if isinstance(cards, list) else "?"
            out.append(Issue(
                "error", where, f"cards needs two to four cards, got {count}",
                "One idea is a title-content slide; five or more is two slides.",
            ))
        else:
            for c_idx, card in enumerate(cards, start=1):
                c_where = f"{where} card {c_idx}"
                if not isinstance(card, dict):
                    out.append(Issue("error", c_where, "card must be an object"))
                    continue
                _unknown_fields(card, "card", c_where, out)
                if not (card.get("title") or card.get("body") or card.get("image")):
                    out.append(Issue("error", c_where, "card has no title, body or image"))
                if card.get("image"):
                    _check_image(card["image"], c_where, base, out)
    elif layout == "cards":
        out.append(Issue("error", where, "cards layout with no `cards`"))

    if slide.get("numbered") and known and layout != "cards":
        out.append(Issue("warning", where, "`numbered` only applies to the cards layout"))

    if slide.get("callout") and known and layout not in CALLOUT_LAYOUTS:
        out.append(Issue(
            "warning", where, f"`callout` doesn't render on the {layout!r} layout",
            "It renders on " + ", ".join(sorted(CALLOUT_LAYOUTS)) + ".",
        ))

    if layout == "quote" and not slide.get("quote"):
        out.append(Issue("error", where, "quote layout with no `quote`"))

    scrim = slide.get("scrim")
    if scrim is not None:
        if scrim not in ("bottom", "left", "none"):
            out.append(Issue(
                "warning", where, f"scrim should be 'bottom', 'left' or 'none', got {scrim!r}",
            ))
        if known and layout != "media-full":
            out.append(Issue("warning", where, "`scrim` only applies to the media-full layout"))


def _design_tips(slide: dict, layout: str | None, where: str, out: list[Issue]) -> None:
    """Judgement calls about how a slide will read from the back of a room."""
    def tip(message: str, hint: str = "") -> None:
        out.append(Issue("tip", where, message, hint))

    heading = _TAG.sub(" ", str(slide.get("heading") or "")).strip()
    if len(heading) > MAX_HEADING_CHARS:
        tip(f"heading is {len(heading)} characters",
            "A heading reads at a glance under ~70. Move the rest into body or notes.")

    body_words = _words(slide.get("body"))
    if body_words > MAX_BODY_WORDS:
        tip(f"body is {body_words} words",
            f"Over ~{MAX_BODY_WORDS} words the room reads instead of listening. "
            "Split the slide or move detail into notes.")

    bullets = slide.get("bullets")
    if isinstance(bullets, list):
        if len(bullets) > MAX_BULLETS:
            tip(f"{len(bullets)} bullets", "Six is about the most a slide can hold. Split it.")
        paired = [b for b in bullets if isinstance(b, dict) and b.get("sub")]
        if layout == "title-content" and 3 <= len(bullets) <= 4 and len(paired) == len(bullets):
            tip("every bullet has a title and a second line",
                "Three or four parallel ideas usually read better as a `cards` layout.")

    if _words(slide.get("callout")) > MAX_CALLOUT_WORDS:
        tip(f"callout is {_words(slide.get('callout'))} words",
            "A callout is the one-line takeaway. Keep it to a sentence or two.")

    for c_idx, card in enumerate(slide.get("cards") or [], start=1):
        if isinstance(card, dict):
            n = _words(card.get("body"))
            if n > MAX_CARD_WORDS:
                tip(f"card {c_idx} body is {n} words",
                    "Cards sit side by side, so each holds a sentence or two at most.")

    if slide.get("quote") and not slide.get("cite"):
        tip("quote has no `cite`", "Say who said it; the room will want to know.")

    total = sum(_words(slide.get(k)) for k in (
        "heading", "subheading", "body", "quote", "callout", "caption"))
    for b in bullets if isinstance(bullets, list) else []:
        total += _words(b.get("text") if isinstance(b, dict) else b)
        total += _words(b.get("sub") if isinstance(b, dict) else "")
    for side in ("left", "right"):
        block = slide.get(side)
        if isinstance(block, dict):
            total += _words(block.get("body"))
            for b in block.get("bullets") or []:
                total += _words(b.get("text") if isinstance(b, dict) else b)
    for card in slide.get("cards") or []:
        if isinstance(card, dict):
            total += _words(card.get("title")) + _words(card.get("body"))
    if total > MAX_SLIDE_WORDS:
        tip(f"{total} words on one slide",
            "A slide the room can take in at a glance is under ~90 words. "
            "Split it, or move the detail into notes.")


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
                      'Use something like ">=2026.11.1".')]
    if ok:
        return []
    return [Issue(
        "error", where,
        f"needs Glissade {requirement}, but this is {__version__}",
        "Run `glissade upgrade`. Presenting anyway will silently skip anything "
        "this release doesn't understand.",
    )]


def check_deck(
    deck: dict[str, Any],
    theme_ids: list[str] | None = None,
    themes: list[dict[str, Any]] | None = None,
) -> list[Issue]:
    """Validate one loaded deck. Media paths resolve beside the deck file.

    `themes` (the project's shared themes, expanded) lets a theme defined
    inside the deck be checked as it will actually be drawn.
    """
    base = Path(deck["path"]).resolve().parent
    label = f"[{deck['id']}] "
    issues = check_requirement(deck, label)
    issues += _deck_level(deck, label, theme_ids, themes)
    return issues + check_slides(deck.get("slides", []), base, label=f"[{deck['id']}]")


def _deck_level(
    deck: dict[str, Any],
    label: str,
    theme_ids: list[str] | None = None,
    themes: list[dict[str, Any]] | None = None,
) -> list[Issue]:
    out: list[Issue] = []
    raw = deck.get("raw")
    if isinstance(raw, dict):
        _unknown_fields(raw, "deckObject", f"{label}deck", out)
        theme = raw.get("theme")
        if isinstance(theme, dict):
            _check_deck_theme(deck, theme, f"{label}deck theme", theme_ids, themes, out)
        elif theme is not None and not isinstance(theme, str):
            out.append(Issue(
                "error", f"{label}deck", "theme must be a theme id or a theme object",
            ))
        elif theme is not None and theme_ids is not None and theme not in theme_ids:
            out.append(Issue(
                "warning", f"{label}deck", f"unknown theme {theme!r}",
                _did_you_mean(str(theme), theme_ids)
                or "Available: " + ", ".join(theme_ids) + ".",
            ))
    return out


_HEX_COLOUR = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _check_deck_theme(
    deck: dict[str, Any],
    spec: dict[str, Any],
    where: str,
    theme_ids: list[str] | None,
    themes: list[dict[str, Any]] | None,
    out: list[Issue],
) -> None:
    """A theme written inside the deck: everything a themes.json entry gets
    checked for, plus what only shows up here."""
    from .project import DEFAULT_THEMES
    from .themes import deck_theme

    _unknown_fields(spec, "deckTheme", where, out)

    parent = spec.get("extends")
    if parent is not None and not isinstance(parent, str):
        out.append(Issue("error", where, "extends must be a theme id"))
    if not any(isinstance(spec.get(k), (dict, str)) for k in ("palette", "vars", "extends")):
        out.append(Issue(
            "warning", where, "theme sets no palette, vars or extends, so it changes nothing",
            'Add "palette": {"dark": ..., "light": ..., "accent": ...}, or "extends".',
        ))

    palette = spec.get("palette")
    if palette is not None and not isinstance(palette, dict):
        out.append(Issue("error", where, "palette must be an object"))
    elif isinstance(palette, dict):
        for key in ("dark", "light", "accent", "accent2"):
            value = palette.get(key)
            if value is not None and not (isinstance(value, str) and _HEX_COLOUR.match(value)):
                out.append(Issue(
                    "warning", where, f"palette {key} {value!r} isn't a hex colour",
                    "Use #rrggbb or #rgb; other colour forms can't be checked for contrast.",
                ))

    variables = spec.get("vars")
    if variables is not None and not isinstance(variables, dict):
        out.append(Issue("error", where, "vars must be an object"))
    elif isinstance(variables, dict):
        for key in variables:
            if not str(key).startswith("--"):
                out.append(Issue(
                    "warning", where, f"vars key {key!r} isn't a CSS custom property",
                    f"Write it as {'--' + str(key).lstrip('-')!r}.",
                ))

    base = Path(deck["path"]).resolve().parent
    fonts = spec.get("fonts")
    if fonts is not None and not isinstance(fonts, list):
        out.append(Issue("error", where, "fonts must be a list"))
    for i, font in enumerate(fonts if isinstance(fonts, list) else [], start=1):
        f_where = f"{where} font {i}"
        if not isinstance(font, dict) or not font.get("family") or not font.get("src"):
            out.append(Issue("error", f_where, "a font needs `family` and `src`"))
            continue
        path = Path(str(font["src"]))
        path = path if path.is_absolute() else base / path
        if not path.is_file():
            out.append(Issue("error", f_where, f"font file not found: {font['src']}"))
        elif path.suffix.lower() not in (".woff2", ".woff", ".ttf", ".otf"):
            out.append(Issue("warning", f_where, f"not a web font file: {font['src']}"))

    built = deck_theme(deck, themes or [], DEFAULT_THEMES)
    if built is None:
        return
    if built.get("_extends_error"):
        hint = ""
        if isinstance(parent, str) and theme_ids:
            available = "Available: " + ", ".join(theme_ids) + "."
            hint = _did_you_mean(parent, theme_ids) or available
        out.append(Issue("error", where, built["_extends_error"], hint))
    out.extend(_contrast(built, where))


def _contrast(theme: dict[str, Any], where: str) -> list[Issue]:
    from .themes import contrast_issues

    return [
        Issue("warning", where, f"low contrast — {problem}",
              "Darken the text colour or lighten the background (WCAG AA is 4.5:1).")
        for problem in contrast_issues(theme)
    ]


def check_themes(themes: list[dict[str, Any]]) -> list[Issue]:
    """Problems in the themes a project will present with."""
    out = []
    for t in themes:
        where = f"theme {t['id']!r}"
        if t.get("_extends_error"):
            out.append(Issue("warning", where, t["_extends_error"],
                             "Its own palette and vars still apply."))
        out.extend(_contrast(t, where))
    return out
