"""Build decks into standalone HTML files.

Each output is the offline fallback — no server, no network, just open it in a
browser. It is rendered from the same template the server uses, so the two
can't drift apart, and local images and activities are inlined so the single
file carries everything with it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .app import load_themes, prepared_slides, render_deck
from .assets import external_media
from .project import Project


class BuildResult:
    """What one built deck turned out to be, for the CLI to report."""

    def __init__(
        self,
        deck: dict[str, Any],
        path: Path,
        warnings: list[str],
        remote: list[tuple[Any, str]],
    ):
        self.deck = deck
        self.path = path
        self.warnings = warnings
        self.remote = remote

    @property
    def size(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0


def build_deck(
    deck: dict[str, Any],
    out_dir: Path,
    themes: list[dict[str, Any]] | None = None,
) -> BuildResult:
    slides, warnings = prepared_slides(deck)
    html = render_deck(
        slides,
        live=False,
        themes=themes if themes is not None else load_themes(),
        title=deck["title"],
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{deck['id']}.html"
    out.write_text(html, encoding="utf-8")
    return BuildResult(deck, out, warnings, external_media(slides))


def build_all(
    project: Project,
    decks: list[dict[str, Any]],
    out_dir: Path | None = None,
) -> list[BuildResult]:
    themes = load_themes(project)
    target = out_dir or project.build_dir
    return [build_deck(deck, target, themes) for deck in decks]
