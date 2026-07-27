"""Where things live.

Slidecast is installed once and run from wherever the user's decks are, so
nothing may be resolved relative to the package except the tool's own assets.

A *project* is any directory containing `decks/`. Commands search upward from
the working directory for one, the way git finds a repository, so `slidecast
start` works from anywhere inside the project.

Two kinds of path, kept deliberately separate:

    RESOURCES   ship inside the wheel and are read-only — templates, the
                default themes, the schema, the init scaffold, the demo decks
    PROJECT     belong to the user and are writable — decks, an optional local
                themes.json, build output, presenter state
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

# --- resources shipped with the tool -------------------------------------

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
DATA_DIR = PACKAGE_DIR / "data"
DEFAULT_THEMES = DATA_DIR / "themes.json"
SCHEMA_FILE = DATA_DIR / "schema.json"
SCAFFOLD_DIR = DATA_DIR / "scaffold"
DEMO_DIR = DATA_DIR / "demo"

# --- the user's project --------------------------------------------------

DECKS_DIRNAME = "decks"
STATE_DIRNAME = ".slidecast"
CONFIG_NAME = "slidecast.toml"


class ProjectNotFound(Exception):
    """Raised when a command needs a project and there isn't one."""

    def __init__(self, start: Path):
        self.start = start
        super().__init__(
            f"no slidecast project in {start} or any parent directory.\n"
            f"Run `slidecast init` here to create one."
        )


@dataclass(frozen=True)
class Project:
    """A directory holding decks, plus everything derived from it."""

    root: Path

    # -- inputs --

    @property
    def decks_dir(self) -> Path:
        return self.root / DECKS_DIRNAME

    @property
    def config_file(self) -> Path:
        return self.root / CONFIG_NAME

    @property
    def themes_file(self) -> Path:
        """A project-local themes.json wins; otherwise the tool's own.

        This is what lets one install serve differently branded projects
        without editing anything inside the package.
        """
        local = self.root / "themes.json"
        return local if local.is_file() else DEFAULT_THEMES

    @property
    def has_local_themes(self) -> bool:
        return (self.root / "themes.json").is_file()

    # -- outputs --

    @property
    def build_dir(self) -> Path:
        return self.root / "build"

    @property
    def state_dir(self) -> Path:
        return self.root / STATE_DIRNAME

    @property
    def state_file(self) -> Path:
        """Which deck, theme and text size were last used.

        Kept inside the project rather than a user-wide config directory: the
        right text size is a property of the room you present that project in,
        not of the machine.
        """
        return self.state_dir / "state.json"

    def config(self) -> dict:
        """Optional defaults from slidecast.toml. Absent or broken is fine.

        tomllib is 3.11+; on 3.10 the file is simply ignored rather than
        dragging in a dependency for an optional convenience.
        """
        if not self.config_file.is_file():
            return {}
        try:
            import tomllib
        except ImportError:
            return {}
        try:
            with self.config_file.open("rb") as fh:
                data = tomllib.load(fh)
            section = data.get("slidecast", data)
            return section if isinstance(section, dict) else {}
        except (OSError, ValueError):
            return {}

    def __str__(self) -> str:  # pragma: no cover - display only
        return str(self.root)


def find_project(start: Path | None = None) -> Project | None:
    """Walk upward looking for a directory that holds decks/."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / DECKS_DIRNAME).is_dir():
            return Project(candidate)
        # An explicit config marks the root even before any deck exists.
        if (candidate / CONFIG_NAME).is_file():
            return Project(candidate)
    return None


def require_project(start: Path | None = None) -> Project:
    here = (start or Path.cwd()).resolve()
    project = find_project(here)
    if project is None:
        raise ProjectNotFound(here)
    return project


def demo_project() -> Project:
    """The decks that ship with the tool, presented as a read-only project.

    `slidecast demo` runs from anywhere, including a directory that has no
    project at all, so a new user can see the thing working before writing a
    single line of JSON.
    """
    return Project(DEMO_DIR)


def is_packaged(project: Project) -> bool:
    """True for the decks that ship inside the wheel."""
    try:
        return PACKAGE_DIR in project.root.resolve().parents or project.root == PACKAGE_DIR
    except OSError:  # pragma: no cover
        return False


def state_path_for(project: Project) -> Path:
    """Where to remember deck, theme and text size.

    Never inside the installed package: that directory may be read-only, and
    even when it isn't, writing there pollutes the install and the state is
    lost on upgrade. The shipped demos keep their state in the user's cache.
    """
    if is_packaged(project) or not os.access(project.root, os.W_OK):
        return _user_cache_dir() / "demo-state.json"
    return project.state_file


def _user_cache_dir() -> Path:
    """Per-OS cache location, created on demand."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    path = base / "slidecast"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:  # pragma: no cover
        from tempfile import gettempdir

        path = Path(gettempdir())
    return path
