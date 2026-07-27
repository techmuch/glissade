"""FastAPI application: slide display, phone remote, and the sync channel."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from . import decks as deck_lib
from .assets import prepare_slides
from .project import TEMPLATE_DIR, Project, state_path_for

# Text-scale limits. Below ~70% the deck stops being readable from the back of
# a room; above ~160% the denser slides need scrolling to read.
MIN_SCALE = 0.7
MAX_SCALE = 1.6
SCALE_STEP = 0.1
DEFAULT_SCALE = 1.0


def clamp_scale(value: Any, fallback: float = DEFAULT_SCALE) -> float:
    """Coerce anything to a usable scale factor, rounded to a clean step."""
    try:
        scale = float(value)
    except (TypeError, ValueError):
        return fallback
    if scale != scale:  # NaN
        return fallback
    return round(min(MAX_SCALE, max(MIN_SCALE, scale)), 2)


def prepared_slides(deck: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """A deck's slides with all local media inlined.

    Media paths resolve against the deck file's own directory, so a deck can
    keep its images beside it.
    """
    base = Path(deck["path"]).resolve().parent
    return prepare_slides(deck["slides"], base)


def load_themes(project: Project | None = None) -> list[dict[str, Any]]:
    """Read the theme definitions. Adding a theme means adding an entry here —
    no code changes, because the deck styles itself entirely from these tokens.

    A missing or broken themes.json must not stop a presentation, so fall back
    to a single built-in theme matching the stylesheet's own defaults.
    """
    from .project import DEFAULT_THEMES

    source = project.themes_file if project else DEFAULT_THEMES
    try:
        with source.open(encoding="utf-8") as fh:
            themes = json.load(fh)
        valid = [
            t
            for t in themes
            if isinstance(t, dict) and t.get("id") and isinstance(t.get("vars"), dict)
        ]
        if valid:
            return valid
    except (OSError, ValueError):
        pass
    return [{"id": "paper", "name": "Paper", "vars": {}}]


def load_settings(
    state_file: Path, theme_ids: list[str], deck_ids: list[str]
) -> dict[str, Any]:
    """Restore presenter preferences from the last run. A missing or corrupt
    file is not worth failing over — fall back to the defaults."""
    default = {
        "scale": DEFAULT_SCALE,
        "theme": theme_ids[0] if theme_ids else "paper",
        "deck": deck_ids[0] if deck_ids else None,
    }
    try:
        with state_file.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return default

    theme, deck = data.get("theme"), data.get("deck")
    return {
        "scale": clamp_scale(data.get("scale")),
        # A theme or deck removed since the last run would leave the deck
        # unstyled or empty, so fall back rather than trusting the file.
        "theme": theme if theme in theme_ids else default["theme"],
        "deck": deck if deck in deck_ids else default["deck"],
    }


def save_settings(state_file: Path, scale: float, theme: str, deck: str | None) -> None:
    """Persist preferences. Best-effort: a read-only project (the shipped
    demos) shouldn't stop a presentation."""
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps({"scale": scale, "theme": theme, "deck": deck}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def render_deck(
    slides: list[dict[str, Any]],
    live: bool,
    themes: list[dict[str, Any]] | None = None,
    title: str = "Glissade",
) -> str:
    """Fill the deck template.

    The same template produces both the live (server-driven) deck and the
    standalone offline file — only the LIVE flag differs, so there is one
    rendering path to keep correct. Every theme is embedded either way, so the
    offline file can switch themes with no server.
    """
    template = (TEMPLATE_DIR / "deck.html").read_text(encoding="utf-8")

    def embed(data: Any) -> str:
        # </script> inside slide markup would close the tag early.
        return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    return (
        template.replace("__SLIDES_JSON__", embed(slides))
        .replace("__THEMES_JSON__", embed(themes if themes is not None else []))
        .replace("__TITLE__", embed(title))
        .replace("__LIVE__", "true" if live else "false")
    )


@dataclass
class Presentation:
    """Current position in the deck, plus the set of connected listeners.

    The server owns this state rather than each browser, so the projector and
    every remote always agree — whoever presses a key, everyone follows.
    """

    total: int
    state_file: Path | None = None
    theme_ids: list[str] = field(default_factory=list)
    deck_ids: list[str] = field(default_factory=list)
    n: int = 1
    blank: bool = False
    scale: float = DEFAULT_SCALE
    theme: str = "paper"
    deck: str | None = None
    # Bumped when the deck changes. Displays reload on a change, because the
    # slides are baked into the page they were served.
    rev: int = 0
    listeners: set[asyncio.Queue] = field(default_factory=set)

    @property
    def state(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "blank": self.blank,
            "scale": self.scale,
            "theme": self.theme,
            "deck": self.deck,
            "rev": self.rev,
            "total": self.total,
            "min_scale": MIN_SCALE,
            "max_scale": MAX_SCALE,
        }

    def goto(self, n: int) -> dict[str, Any]:
        try:
            target = int(n)
        except (TypeError, ValueError):
            target = self.n
        self.n = max(1, min(self.total, target))
        return self.publish()

    def step(self, delta: int) -> dict[str, Any]:
        return self.goto(self.n + delta)

    def set_blank(self, blank: bool) -> dict[str, Any]:
        self.blank = bool(blank)
        return self.publish()

    def set_scale(self, scale: Any) -> dict[str, Any]:
        self.scale = clamp_scale(scale, fallback=self.scale)
        self._save()
        return self.publish()

    def bump_scale(self, steps: int) -> dict[str, Any]:
        return self.set_scale(self.scale + steps * SCALE_STEP)

    def set_theme(self, theme: Any) -> dict[str, Any]:
        # Ignore unknown ids rather than leaving the deck with no tokens.
        if theme in self.theme_ids:
            self.theme = theme
            self._save()
        return self.publish()

    def cycle_theme(self, steps: int = 1) -> dict[str, Any]:
        if not self.theme_ids:
            return self.state
        idx = self.theme_ids.index(self.theme) if self.theme in self.theme_ids else 0
        return self.set_theme(self.theme_ids[(idx + steps) % len(self.theme_ids)])

    def _save(self) -> None:
        if self.state_file is not None:
            save_settings(self.state_file, self.scale, self.theme, self.deck)

    def publish(self) -> dict[str, Any]:
        state = self.state
        for q in list(self.listeners):
            try:
                q.put_nowait(state)
            except asyncio.QueueFull:  # pragma: no cover - a stalled client
                self.listeners.discard(q)
        return state


def create_app(project: Project, deck_name: str | None = None) -> FastAPI:
    all_decks = deck_lib.discover(project)
    if not all_decks:
        raise SystemExit(
            f"No decks found in {project.decks_dir}.\n"
            f"Add a .json file there, or run `glissade init` to scaffold one."
        )

    themes = load_themes(project)
    state_file = state_path_for(project)
    theme_ids = [t["id"] for t in themes]
    deck_ids = [d["id"] for d in all_decks]
    settings = load_settings(state_file, theme_ids, deck_ids)

    current = deck_lib.resolve(deck_name or settings["deck"], all_decks)

    app = FastAPI(title="Glissade", docs_url=None, redoc_url=None)

    # Slides are prepared (media inlined) once per deck and cached, since
    # base64-encoding images on every request would be wasteful.
    cache: dict[str, list[dict[str, Any]]] = {}

    def slides_for(deck: dict[str, Any]) -> list[dict[str, Any]]:
        if deck["id"] not in cache:
            prepared, warnings = prepared_slides(deck)
            for w in warnings:
                print(f"  ! [{deck['id']}] {w}")
            cache[deck["id"]] = prepared
        return cache[deck["id"]]

    def deck_by_id(deck_id: str | None) -> dict[str, Any]:
        for d in all_decks:
            if d["id"] == deck_id:
                return d
        return current

    show = Presentation(
        total=len(slides_for(current)),
        state_file=state_file,
        theme_ids=theme_ids,
        deck_ids=deck_ids,
        scale=settings["scale"],
        theme=settings["theme"],
        deck=current["id"],
    )
    app.state.show = show
    app.state.decks = all_decks
    app.state.project = project

    def switch(deck_id: str) -> dict[str, Any]:
        """Change the running deck. Bumps `rev` so open displays reload —
        their slides were baked into the page they were served."""
        if deck_id not in deck_ids or deck_id == show.deck:
            return show.state
        deck = deck_by_id(deck_id)
        show.deck = deck["id"]
        show.total = len(slides_for(deck))
        show.n = 1
        show.blank = False
        show.rev += 1
        show._save()
        return show.publish()

    def no_store(html: str) -> HTMLResponse:
        # Phones aggressively cache; a stale page mid-presentation is no fun.
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.get("/", response_class=HTMLResponse)
    async def display() -> HTMLResponse:
        """The projected deck."""
        deck = deck_by_id(show.deck)
        return no_store(
            render_deck(slides_for(deck), live=True, themes=themes, title=deck["title"])
        )

    @app.get("/control", response_class=HTMLResponse)
    async def control() -> HTMLResponse:
        """The phone remote: current notes, next-slide preview, jump list."""
        return no_store((TEMPLATE_DIR / "control.html").read_text(encoding="utf-8"))

    @app.get("/api/slides")
    async def api_slides() -> JSONResponse:
        return JSONResponse(
            slides_for(deck_by_id(show.deck)), headers={"Cache-Control": "no-store"}
        )

    @app.get("/api/themes")
    async def api_themes() -> JSONResponse:
        return JSONResponse(themes, headers={"Cache-Control": "no-store"})

    @app.get("/api/decks")
    async def api_decks() -> JSONResponse:
        return JSONResponse(
            deck_lib.summaries(all_decks), headers={"Cache-Control": "no-store"}
        )

    @app.get("/api/state")
    async def api_state() -> dict[str, Any]:
        return show.state

    @app.post("/api/goto")
    async def api_goto(body: dict[str, Any]) -> dict[str, Any]:
        return show.goto(body.get("n", 1))

    @app.post("/api/next")
    async def api_next() -> dict[str, Any]:
        return show.step(1)

    @app.post("/api/prev")
    async def api_prev() -> dict[str, Any]:
        return show.step(-1)

    @app.post("/api/blank")
    async def api_blank(body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        return show.set_blank(body.get("blank", not show.blank))

    @app.post("/api/scale")
    async def api_scale(body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Set the deck's text size.

        Accepts either an absolute `scale` (1.0 = as designed) or a relative
        `step` (+1 / -1). The chosen size is written to disk so it survives a
        restart — set it once while pointing at the projector and it's still
        right when you start.
        """
        body = body or {}
        if "scale" in body:
            return show.set_scale(body["scale"])
        try:
            steps = int(body.get("step", 0))
        except (TypeError, ValueError):
            steps = 0
        return show.bump_scale(steps)

    @app.post("/api/theme")
    async def api_theme(body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Switch the deck's theme.

        Accepts an `id` from themes.json, or `step: 1` to cycle. Unknown ids
        are ignored — better to keep presenting in the current theme than to
        strip the deck of its tokens mid-presentation.
        """
        body = body or {}
        if "id" in body:
            return show.set_theme(body["id"])
        try:
            steps = int(body.get("step", 1))
        except (TypeError, ValueError):
            steps = 1
        return show.cycle_theme(steps)

    @app.post("/api/deck")
    async def api_deck(body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Switch to a different deck. Displays reload themselves."""
        body = body or {}
        return switch(str(body.get("id", "")))

    @app.get("/events")
    async def events() -> StreamingResponse:
        """Server-sent events: one message per state change, plus a heartbeat
        so phone browsers and Wi-Fi routers don't drop an idle connection."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=32)
        show.listeners.add(queue)

        async def stream():
            try:
                yield f"data: {json.dumps(show.state)}\n\n"
                while True:
                    try:
                        state = await asyncio.wait_for(queue.get(), timeout=15)
                        yield f"data: {json.dumps(state)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
            finally:
                show.listeners.discard(queue)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    return app
