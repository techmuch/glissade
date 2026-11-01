"""FastAPI application: slide display, phone remote, and the sync channel."""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import ipaddress
import json
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from . import decks as deck_lib
from .assets import prepare_slides
from .project import TEMPLATE_DIR, Project, state_path_for

# Not print(): a Windows console or pipe may not encode "↻", and a failed
# print inside the watcher would be reported as a failed reload.
from .term import out as say

# Text-scale limits. Below ~70% the deck stops being readable from the back of
# a room; above ~160% the denser slides need scrolling to read.
MIN_SCALE = 0.7
MAX_SCALE = 1.6
SCALE_STEP = 0.1
DEFAULT_SCALE = 1.0

# How long an idle event stream waits before sending a comment, to stop routers
# and phone browsers dropping it.
HEARTBEAT_SECONDS = 15

# The live server polls the project for changes so authoring can happen with
# the deck open. Stdlib polling keeps the install compiler-free everywhere.
WATCH_INTERVAL_SECONDS = 0.25
WATCH_DEBOUNCE_SECONDS = 0.15


def new_control_key() -> str:
    """A short random key for the remote's URL. Short, because it rides in a
    QR code and may be typed by hand; random enough that nobody else on the
    venue's Wi-Fi can guess it during a talk."""
    return secrets.token_urlsafe(8)


def is_loopback(host: str | None) -> bool:
    """True for a request from this machine. The projector usually runs
    here, and keyboard control on it must keep working with no key."""
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


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
    from . import themes as theme_lib
    from .project import DEFAULT_THEMES

    source = project.themes_file if project else DEFAULT_THEMES
    try:
        valid = theme_lib.load(source, builtin=DEFAULT_THEMES)
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


def load_live_notes(notes_file: Path) -> dict[str, dict[str, str]]:
    """Restore presenter-written notes captured during a live session."""
    try:
        with notes_file.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}

    out: dict[str, dict[str, str]] = {}
    if not isinstance(data, dict):
        return out
    for deck, entries in data.items():
        if not isinstance(deck, str) or not isinstance(entries, dict):
            continue
        cleaned = {
            str(n): str(text)
            for n, text in entries.items()
            if str(text).strip()
        }
        if cleaned:
            out[deck] = cleaned
    return out


def save_live_notes(notes_file: Path, notes: dict[str, dict[str, str]]) -> None:
    """Persist live notes typed during the meeting. Best-effort."""
    try:
        notes_file.parent.mkdir(parents=True, exist_ok=True)
        notes_file.write_text(json.dumps(notes, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def project_snapshot(project: Project) -> dict[str, tuple[int, int] | None]:
    """A cheap fingerprint of the files a live presentation depends on.

    Deck JSON and deck-local media all live under decks/, so watching that tree
    catches both rewritten slides and swapped images. The local themes.json is
    tracked even when absent, so creating or deleting it also reloads clients.
    """
    snapshot: dict[str, tuple[int, int] | None] = {}

    if project.decks_dir.is_dir():
        for path in sorted(project.decks_dir.rglob("*")):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshot[str(path.resolve())] = (stat.st_mtime_ns, stat.st_size)

    local_themes = project.root / "themes.json"
    if local_themes.is_file():
        try:
            stat = local_themes.stat()
            snapshot[str(local_themes.resolve())] = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            snapshot[str(local_themes.resolve())] = None
    else:
        snapshot[str(local_themes.resolve())] = None

    return snapshot


def discover_live_decks(project: Project) -> list[dict[str, Any]]:
    """Read the project's decks, but fail on any broken JSON file.

    `deck_lib.discover()` skips unreadable decks for CLI listing and checking,
    which is friendly there. Live reload wants the opposite trade: one half-
    written file from an editor or AI should keep the last good presentation on
    screen instead of silently swapping to a different subset of decks.
    """
    decks = deck_lib.discover(project)
    expected = {str(path.resolve()) for path in sorted(project.decks_dir.glob("*.json"))}
    seen = {str(Path(deck["path"]).resolve()) for deck in decks}
    skipped = sorted(Path(path).name for path in expected - seen)
    if skipped:
        names = ", ".join(skipped)
        raise ValueError(f"can't reload until these deck files parse again: {names}")
    return decks


def render_deck(
    slides: list[dict[str, Any]],
    live: bool,
    themes: list[dict[str, Any]] | None = None,
    title: str = "Glissade",
    decks: list[dict[str, Any]] | None = None,
    current_deck_id: str | None = None,
    deck_theme: str = "",
) -> str:
    """Fill the deck template.

    The same template produces both the live (server-driven) deck and the
    standalone offline file — only the LIVE flag differs, so there is one
    rendering path to keep correct. Every theme is embedded either way, so the
    offline file can switch themes with no server.
    """
    template = deck_template()

    def embed(data: Any) -> str:
        # </script> inside slide markup would close the tag early.
        return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    from . import themes as theme_lib

    themes = themes if themes is not None else []
    # Font files can be large, so they are inlined once as CSS rather than
    # riding along inside the theme JSON.
    values = {
        "/*__FONT_FACES__*/": theme_lib.font_face_css(themes).replace("</", "<\\/"),
        "__SLIDES_JSON__": embed(slides),
        "__THEMES_JSON__": embed(theme_lib.public(themes)),
        "__DECK_THEME__": embed(deck_theme or ""),
        "__DECKS_JSON__": embed(decks if decks is not None else []),
        "__CURRENT_DECK__": embed(current_deck_id or ""),
        "__TITLE__": embed(title),
        "__LIVE__": "true" if live else "false",
    }
    # One pass, so text that was just inserted is never searched again: a slide
    # that happens to say "__TITLE__" must come out saying exactly that.
    return _PLACEHOLDER.sub(lambda m: values[m.group(0)], template)


_PLACEHOLDER = re.compile(
    r"/\*__FONT_FACES__\*/|__(?:SLIDES_JSON|THEMES_JSON|DECK_THEME|DECKS_JSON"
    r"|CURRENT_DECK|TITLE|LIVE)__"
)


def deck_template() -> str:
    """deck.html with its stylesheet and script inlined.

    They are kept as separate files so each can be read, edited and checked
    on its own; the page that ships is still one self-contained file.
    """
    def part(name: str) -> str:
        return (TEMPLATE_DIR / name).read_text(encoding="utf-8")

    return (
        part("deck.html")
        .replace("/*__DECK_CSS__*/", part("deck.css"), 1)
        .replace("/*__DECK_JS__*/", part("deck.js"), 1)
    )


@dataclass
class Presentation:
    """Current position in the deck, plus the set of connected listeners.

    The server owns this state rather than each browser, so the projector and
    every remote always agree — whoever presses a key, everyone follows.
    """

    total: int
    state_file: Path | None = None
    notes_file: Path | None = None
    theme_ids: list[str] = field(default_factory=list)
    deck_ids: list[str] = field(default_factory=list)
    n: int = 1
    blank: bool = False
    scale: float = DEFAULT_SCALE
    theme: str = "paper"
    deck: str | None = None
    live_notes: dict[str, dict[str, str]] = field(default_factory=dict)
    live_notes_visible: bool = False
    # Bumped when the deck changes. Displays reload on a change, because the
    # slides are baked into the page they were served.
    rev: int = 0
    listeners: set[asyncio.Queue] = field(default_factory=set)
    reload_error: str = ""

    def live_note_for(self, n: int | None = None, deck: str | None = None) -> str:
        deck_id = deck if deck is not None else self.deck
        if not deck_id:
            return ""
        slide = self.n if n is None else n
        return str(self.live_notes.get(deck_id, {}).get(str(slide), ""))

    def live_notes_for_current_deck(self) -> list[dict[str, Any]]:
        if not self.deck:
            return []
        deck_notes = self.live_notes.get(self.deck, {})
        out = []
        for key, text in sorted(deck_notes.items(), key=lambda item: int(item[0])):
            out.append({"n": int(key), "text": str(text)})
        return out

    @property
    def state(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "blank": self.blank,
            "scale": self.scale,
            "theme": self.theme,
            "deck": self.deck,
            "live_note": self.live_note_for(),
            "live_notes_visible": self.live_notes_visible,
            "rev": self.rev,
            "total": self.total,
            "min_scale": MIN_SCALE,
            "max_scale": MAX_SCALE,
            "all_live_notes": self.live_notes_for_current_deck(),
            "reload_error": self.reload_error,
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

    def set_live_note(self, text: Any, n: Any = None) -> dict[str, Any]:
        if not self.deck:
            return self.state
        try:
            target = self.n if n is None else int(n)
        except (TypeError, ValueError):
            target = self.n
        target = max(1, min(self.total, target))
        deck_notes = self.live_notes.setdefault(self.deck, {})
        note = str(text or "")
        if note.strip():
            deck_notes[str(target)] = note
        else:
            deck_notes.pop(str(target), None)
            if not deck_notes:
                self.live_notes.pop(self.deck, None)
        self._save_live_notes()
        if target == self.n:
            return self.publish()
        return self.state

    def set_live_notes_visible(self, visible: Any) -> dict[str, Any]:
        self.live_notes_visible = bool(visible)
        return self.publish()

    def _save(self) -> None:
        if self.state_file is not None:
            save_settings(self.state_file, self.scale, self.theme, self.deck)

    def _save_live_notes(self) -> None:
        if self.notes_file is not None:
            save_live_notes(self.notes_file, self.live_notes)

    def publish(self) -> dict[str, Any]:
        state = self.state
        for q in list(self.listeners):
            try:
                q.put_nowait(state)
            except asyncio.QueueFull:  # pragma: no cover - a stalled client
                self.listeners.discard(q)
        return state


def create_app(
    project: Project,
    deck_name: str | None = None,
    *,
    watch: bool = False,
    watch_interval: float = WATCH_INTERVAL_SECONDS,
    watch_debounce: float = WATCH_DEBOUNCE_SECONDS,
    control_key: str | None = None,
) -> FastAPI:
    """Build the server.

    With a `control_key`, commands (every POST under /api/) from another
    machine must carry it, as an `X-Glissade-Key` header or `?k=` query.
    Reading — the slides, the state, the event stream — stays open, so a
    second screen can follow along without the key.
    """
    all_decks = deck_lib.discover(project)
    if not all_decks:
        raise SystemExit(
            f"No decks found in {project.decks_dir}.\n"
            f"Add a .json file there, or run `glissade init` to scaffold one."
        )

    from . import themes as theme_lib
    from .project import DEFAULT_THEMES

    # Shared themes: the project's themes.json, or the built-in set.
    themes = load_themes(project)
    state_file = state_path_for(project)
    deck_ids = [d["id"] for d in all_decks]

    def themes_open(deck: dict[str, Any] | None) -> list[dict[str, Any]]:
        """What the picker offers while `deck` is open: its own inline theme,
        if it defines one, then the shared themes."""
        return theme_lib.for_deck(themes, deck, DEFAULT_THEMES)

    def ids(ts: list[dict[str, Any]]) -> list[str]:
        return [t["id"] for t in ts]

    # The saved theme may belong to any deck, so accept every deck's own id
    # here; it's narrowed to the open deck's below.
    known_theme_ids = ids(themes) + [
        theme_lib.deck_theme_id(d["id"]) for d in all_decks if d.get("theme_spec")
    ]
    settings = load_settings(state_file, known_theme_ids, deck_ids)
    notes_file = state_file.with_name("live-notes.json")
    live_notes = load_live_notes(notes_file)

    current = deck_lib.resolve(deck_name or settings["deck"], all_decks)
    theme_ids = ids(themes_open(current))

    def opening_theme(deck: dict[str, Any], fallback: str) -> str:
        """A deck that names its theme opens in it; otherwise keep `fallback`
        if this deck offers it. The presenter can still change it with T or
        from the remote."""
        if deck.get("theme") in theme_ids:
            return deck["theme"]
        if fallback in theme_ids:
            return fallback
        return theme_ids[0] if theme_ids else "paper"

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        if watch:
            app.state.watch_task = asyncio.create_task(watch_project())
        try:
            yield
        finally:
            task = getattr(app.state, "watch_task", None)
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="Glissade", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.control_key = control_key

    def require_key(request: Request) -> None:
        if not control_key or is_loopback(request.client.host if request.client else None):
            return
        given = request.headers.get("x-glissade-key") or request.query_params.get("k") or ""
        if not hmac.compare_digest(given.encode(), control_key.encode()):
            raise HTTPException(status_code=403, detail="missing or wrong control key")

    guarded = [Depends(require_key)]

    # Slides are prepared (media inlined) once per deck and cached, since
    # base64-encoding images on every request would be wasteful.
    cache: dict[str, list[dict[str, Any]]] = {}

    def slides_for(deck: dict[str, Any]) -> list[dict[str, Any]]:
        if deck["id"] not in cache:
            prepared, warnings = prepared_slides(deck)
            for w in warnings:
                say(f"  ! [{deck['id']}] {w}")
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
        notes_file=notes_file,
        theme_ids=theme_ids,
        deck_ids=deck_ids,
        scale=settings["scale"],
        theme=opening_theme(current, settings["theme"]),
        deck=current["id"],
        live_notes=live_notes,
    )
    app.state.show = show
    app.state.decks = all_decks
    app.state.project = project
    app.state.themes = themes

    def reload_project_state() -> dict[str, Any]:
        """Reload decks, themes and prepared assets after an on-disk change.

        Reload is atomic from the clients' point of view: either the new files
        parse and everyone is told to refresh, or the last good presentation
        keeps running and only an error message changes.
        """
        nonlocal all_decks, current, themes, theme_ids, deck_ids

        new_decks = discover_live_decks(project)
        if not new_decks:
            raise ValueError(f"no readable decks found in {project.decks_dir}")
        new_themes = load_themes(project)
        new_deck_ids = [d["id"] for d in new_decks]
        selected = show.deck if show.deck in new_deck_ids else None
        new_current = deck_lib.resolve(selected, new_decks)
        if new_current is None:
            raise ValueError(f"no readable decks found in {project.decks_dir}")

        all_decks = new_decks
        current = new_current
        themes = new_themes
        theme_ids = ids(themes_open(new_current))
        deck_ids = new_deck_ids
        cache.clear()

        show.deck_ids = new_deck_ids
        show.theme_ids = theme_ids
        show.deck = new_current["id"]
        if show.theme not in theme_ids:
            show.theme = opening_theme(new_current, show.theme)
        show.total = len(slides_for(new_current))
        show.n = max(1, min(show.total, show.n))
        show.reload_error = ""
        show.rev += 1
        show._save()
        app.state.decks = all_decks
        app.state.themes = themes
        return show.publish()

    async def watch_project() -> None:
        snapshot = project_snapshot(project)
        while True:
            await asyncio.sleep(watch_interval)
            latest = project_snapshot(project)
            if latest == snapshot:
                continue
            await asyncio.sleep(watch_debounce)
            latest = project_snapshot(project)
            if latest == snapshot:
                continue
            snapshot = latest
            try:
                state = reload_project_state()
                deck = deck_by_id(show.deck)
                say(f"  ↻ reloaded {deck['id']} ({len(deck['slides'])} slides)")
            except Exception as exc:
                show.reload_error = str(exc)
                state = show.publish()
                say(f"  ! reload failed: {exc}")
            app.state.last_reload_state = state

    app.state.reload_project = reload_project_state

    def switch(deck_id: str) -> dict[str, Any]:
        """Change the running deck. Bumps `rev` so open displays reload —
        their slides were baked into the page they were served."""
        nonlocal theme_ids
        if deck_id not in deck_ids or deck_id == show.deck:
            return show.state
        deck = deck_by_id(deck_id)
        show.deck = deck["id"]
        theme_ids = ids(themes_open(deck))
        show.theme_ids = theme_ids
        show.theme = opening_theme(deck, show.theme)
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
        deck_summaries = [
            {
                "id": d["id"],
                "title": d.get("title", d["id"]),
                "subtitle": d.get("subtitle", ""),
                "count": len(d.get("slides", [])),
            }
            for d in app.state.decks
        ]
        return no_store(
            render_deck(
                slides_for(deck),
                live=True,
                themes=themes_open(deck),
                title=deck["title"],
                decks=deck_summaries,
                current_deck_id=deck["id"],
                deck_theme=deck.get("theme", ""),
            )
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
        return JSONResponse(
            theme_lib.public(themes_open(deck_by_id(show.deck))),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/decks")
    async def api_decks() -> JSONResponse:
        return JSONResponse(
            deck_lib.summaries(all_decks), headers={"Cache-Control": "no-store"}
        )

    @app.get("/api/state")
    async def api_state() -> dict[str, Any]:
        return show.state

    @app.post("/api/goto", dependencies=guarded)
    async def api_goto(body: dict[str, Any]) -> dict[str, Any]:
        return show.goto(body.get("n", 1))

    @app.post("/api/next", dependencies=guarded)
    async def api_next() -> dict[str, Any]:
        return show.step(1)

    @app.post("/api/prev", dependencies=guarded)
    async def api_prev() -> dict[str, Any]:
        return show.step(-1)

    @app.post("/api/blank", dependencies=guarded)
    async def api_blank(body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        return show.set_blank(body.get("blank", not show.blank))

    @app.post("/api/scale", dependencies=guarded)
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

    @app.post("/api/theme", dependencies=guarded)
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

    @app.post("/api/deck", dependencies=guarded)
    async def api_deck(body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Switch to a different deck. Displays reload themselves."""
        body = body or {}
        return switch(str(body.get("id", "")))

    @app.get("/api/live-notes")
    async def api_live_notes() -> dict[str, Any]:
        return {
            "deck": show.deck,
            "n": show.n,
            "text": show.live_note_for(),
            "visible": show.live_notes_visible,
            "all": show.live_notes_for_current_deck(),
        }

    @app.post("/api/live-notes", dependencies=guarded)
    async def api_live_notes_set(body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        state = show.set_live_note(body.get("text", ""), n=body.get("n"))
        state = dict(state)
        state["all_live_notes"] = show.live_notes_for_current_deck()
        return state

    @app.post("/api/live-notes-visible", dependencies=guarded)
    async def api_live_notes_visible(body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        state = show.set_live_notes_visible(body.get("visible", not show.live_notes_visible))
        state = dict(state)
        state["all_live_notes"] = show.live_notes_for_current_deck()
        return state

    @app.get("/events")
    async def events() -> StreamingResponse:
        """Server-sent events: one message per state change, plus a heartbeat
        so phone browsers and Wi-Fi routers don't drop an idle connection.

        This stream is deliberately endless, which makes it the one thing that
        can stop the process exiting: uvicorn's shutdown waits for open
        connections to finish, and an endless response never does. So the loop
        wakes once a second to check whether the server is shutting down and
        returns if it is -- otherwise Ctrl-C appears to be ignored for as long
        as any browser has the deck open.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=32)
        show.listeners.add(queue)

        async def stream():
            server = getattr(app.state, "server", None)
            idle = 0
            try:
                yield f"data: {json.dumps(show.state)}\n\n"
                while True:
                    if server is not None and server.should_exit:
                        return
                    try:
                        state = await asyncio.wait_for(queue.get(), timeout=1.0)
                        yield f"data: {json.dumps(state)}\n\n"
                        idle = 0
                    except asyncio.TimeoutError:
                        idle += 1
                        if idle >= HEARTBEAT_SECONDS:
                            yield ": keep-alive\n\n"
                            idle = 0
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
