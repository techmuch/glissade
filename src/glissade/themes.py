"""Themes: loading, palette shorthand, contrast checks and embedded fonts.

A theme is a set of CSS custom properties the deck reads from :root. Writing
all seventeen of them by hand is how palettes end up with unreadable text, so
a theme may instead give a short `palette` — one dark, one light and one or two
accents — and the rest is derived here. Anything in `vars` still wins, so a
derived theme can be nudged one token at a time.

A theme may also bring its own font files. They are embedded into the page as
`@font-face` rules, so a deck that uses them still works with no network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# The text/background pairs the deck actually draws, with the minimum ratio
# each needs. Small text everywhere on a projector, so AA for normal text.
CONTRAST_PAIRS: list[tuple[str, str, float, str]] = [
    ("--ink", "--paper", 4.5, "body text"),
    ("--ink-soft", "--paper", 4.5, "secondary text"),
    ("--accent", "--paper", 4.5, "eyebrows and citations"),
    ("--ink-soft", "--story-bg", 4.5, "secondary text on story slides"),
    ("--ask-ink", "--ask-bg", 4.5, "text on discussion slides"),
    ("--ask-ink-soft", "--ask-bg", 4.5, "secondary text on discussion slides"),
    ("--ask-accent", "--ask-bg", 4.5, "eyebrows on discussion slides"),
    ("--callout-ink", "--callout-bg", 4.5, "callout text"),
    ("--ask-callout-ink", "--ask-callout-bg", 4.5, "callout text on discussion slides"),
]

# What the stylesheet falls back to when a theme doesn't set a token. Used so
# contrast is checked against what will actually be drawn.
DEFAULT_VARS: dict[str, str] = {
    "--ink": "#1e2430",
    "--ink-soft": "#4a5568",
    "--paper": "#f6f3ee",
    "--accent": "#7a5c2e",
    "--accent-light": "#b8955a",
    "--rule": "#ddd5c8",
    "--story-bg": "#efe9df",
    "--ask-bg": "#2f3a3f",
    "--ask-ink": "#e8e2d6",
    "--ask-ink-soft": "#c3cbcd",
    "--ask-heading": "#ffffff",
    "--ask-accent": "#b8955a",
}

FONT_FORMATS = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}
FONT_MIME = {
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
}

_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


# ------------------------------------------------------------------ colour


def parse_hex(value: Any) -> tuple[int, int, int] | None:
    """`#abc` or `#aabbcc` to an RGB tuple; anything else is None."""
    if not isinstance(value, str):
        return None
    m = _HEX.match(value.strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def mix(a: str, b: str, amount: float) -> str:
    """`amount` of the way from colour a to colour b."""
    ra, rb = parse_hex(a), parse_hex(b)
    if not ra or not rb:
        return a
    return to_hex(tuple(x + (y - x) * amount for x, y in zip(ra, rb, strict=True)))


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float | None:
    """WCAG contrast ratio between two hex colours, or None if either isn't
    a plain hex colour (gradients, rgba and named colours aren't judged)."""
    ra, rb = parse_hex(a), parse_hex(b)
    if not ra or not rb:
        return None
    la, lb = _luminance(ra), _luminance(rb)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _toward_contrast(fg: str, bg: str, target: float, toward: str) -> str:
    """Move fg toward `toward` until it reaches `target` contrast on bg."""
    if (contrast(fg, bg) or 0) >= target:
        return fg
    for step in range(1, 21):
        candidate = mix(fg, toward, step / 20)
        if (contrast(candidate, bg) or 0) >= target:
            return candidate
    return toward


# ----------------------------------------------------------------- palette


def expand_palette(palette: dict[str, Any]) -> dict[str, str]:
    """Derive the full token set from a dark, a light and one or two accents.

    Every derived text colour is pushed until it clears WCAG AA against the
    background it sits on, so a palette shorthand can't produce unreadable
    text even when the accent is a mid-tone.
    """
    dark = palette.get("dark") or "#1e2430"
    light = palette.get("light") or "#f6f3ee"
    accent = palette.get("accent") or mix(dark, light, 0.35)
    accent2 = palette.get("accent2")

    paper = light
    accent_text = _toward_contrast(accent, paper, 4.5, dark)
    ask_bg = dark
    ask_accent = _toward_contrast(accent2 or mix(accent, light, 0.45), ask_bg, 4.5, light)

    out = {
        "--paper": paper,
        "--ink": dark,
        "--ink-soft": _toward_contrast(mix(dark, light, 0.28), paper, 5.5, dark),
        "--accent": accent_text,
        "--accent-light": accent2 or mix(accent, light, 0.3),
        "--rule": mix(dark, light, 0.84),
        "--surround": mix(dark, "#000000", 0.35),
        "--story-bg": mix(light, dark, 0.06),
        "--card-bg": mix(light, "#ffffff", 0.55),
        "--ask-bg": ask_bg,
        "--ask-ink": mix(light, dark, 0.06),
        "--ask-ink-soft": _toward_contrast(mix(light, dark, 0.22), ask_bg, 5.5, light),
        "--ask-heading": light,
        "--ask-accent": ask_accent,
        "--callout-bg": accent_text,
        "--callout-ink": paper,
        "--ask-callout-bg": ask_accent,
        "--ask-callout-ink": ask_bg,
        "--overlay-bg": mix(dark, "#000000", 0.4),
        "--overlay-ink": light,
        "--chrome-ink": mix(dark, light, 0.5),
        "--blank-bg": mix(dark, "#000000", 0.6),
    }
    if palette.get("display_font"):
        out["--display-font"] = str(palette["display_font"])
    if palette.get("body_font"):
        out["--body-font"] = str(palette["body_font"])
    return out


def expand_theme(theme: dict[str, Any], base: Path | None = None) -> dict[str, Any]:
    """Return a copy of a theme with its palette expanded and fonts resolved."""
    t = dict(theme)
    variables: dict[str, str] = {}
    if isinstance(t.get("palette"), dict):
        variables.update(expand_palette(t["palette"]))
    if isinstance(t.get("vars"), dict):
        variables.update(t["vars"])
    t["vars"] = variables

    fonts = []
    for spec in t.get("fonts") or []:
        if not isinstance(spec, dict) or not spec.get("family") or not spec.get("src"):
            continue
        src = Path(str(spec["src"]))
        if not src.is_absolute() and base is not None:
            src = base / src
        fonts.append({**spec, "path": str(src)})
    if fonts:
        t["fonts"] = fonts
    else:
        t.pop("fonts", None)
    return t


def resolved_vars(theme: dict[str, Any]) -> dict[str, str]:
    """The token values the stylesheet will actually use for this theme."""
    v = {**DEFAULT_VARS, **(theme.get("vars") or {})}
    v.setdefault("--callout-bg", v["--accent"])
    v.setdefault("--callout-ink", v["--paper"])
    v.setdefault("--ask-callout-bg", v["--ask-accent"])
    v.setdefault("--ask-callout-ink", v["--ask-bg"])
    return v


def contrast_issues(theme: dict[str, Any]) -> list[str]:
    """Plain-language reasons this theme would be hard to read."""
    v = resolved_vars(theme)
    out = []
    for fg, bg, need, what in CONTRAST_PAIRS:
        ratio = contrast(v.get(fg, ""), v.get(bg, ""))
        if ratio is not None and ratio < need:
            out.append(
                f"{what}: {fg} {v[fg]} on {bg} {v[bg]} is {ratio:.2f}:1, needs {need}:1"
            )
    return out


# ------------------------------------------------------------------- load


def load(source: Path) -> list[dict[str, Any]]:
    """Read and expand every valid theme in a themes.json file."""
    with source.open(encoding="utf-8") as fh:
        themes = json.load(fh)
    out = []
    for t in themes if isinstance(themes, list) else []:
        if not isinstance(t, dict) or not t.get("id"):
            continue
        if not isinstance(t.get("vars"), dict) and not isinstance(t.get("palette"), dict):
            continue
        out.append(expand_theme(t, source.parent))
    return out


def public(themes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Themes as sent to browsers: no local file paths."""
    clean = []
    for t in themes:
        c = {k: v for k, v in t.items() if k not in ("fonts", "_palette")}
        if t.get("fonts"):
            c["fonts"] = [f.get("family") for f in t["fonts"]]
        clean.append(c)
    return clean


def font_face_css(themes: list[dict[str, Any]], warnings: list[str] | None = None) -> str:
    """@font-face rules for every font file the themes bring, inlined."""
    from .assets import data_uri

    rules = []
    seen = set()
    for t in themes:
        for spec in t.get("fonts") or []:
            path = Path(spec["path"])
            key = (spec["family"], str(path), spec.get("weight"), spec.get("style"))
            if key in seen:
                continue
            seen.add(key)
            uri = data_uri(path, warnings)
            if not uri:
                continue
            fmt = FONT_FORMATS.get(path.suffix.lower(), "")
            family = str(spec["family"]).replace('"', "")
            rule = f'@font-face{{font-family:"{family}";src:url({uri})'
            rule += f' format("{fmt}")' if fmt else ""
            rule += f";font-weight:{spec.get('weight', '400')}"
            rule += f";font-style:{spec.get('style', 'normal')};font-display:swap}}"
            rules.append(rule)
    return "\n".join(rules)
