"""Glissade — presentation decks that work when the network doesn't.

Decks are JSON. The server drives a projector and a phone remote in sync over
server-sent events. `glissade build` turns a deck into one HTML file with
every image and activity embedded, so a presentation survives a room with no
Wi-Fi.

Installed as a CLI:

    glissade init      scaffold a project in the current directory
    glissade start     present
    glissade build     write standalone HTML
    glissade check     validate decks before you rely on them
"""

__version__ = "0.8.1"

from .project import (  # noqa: F401
    DATA_DIR,
    DEFAULT_THEMES,
    DEMO_DIR,
    PACKAGE_DIR,
    SCAFFOLD_DIR,
    SCHEMA_FILE,
    TEMPLATE_DIR,
    Project,
    ProjectNotFound,
    demo_project,
    find_project,
    require_project,
)

__all__ = [
    "__version__",
    "PACKAGE_DIR",
    "TEMPLATE_DIR",
    "DATA_DIR",
    "DEFAULT_THEMES",
    "SCHEMA_FILE",
    "SCAFFOLD_DIR",
    "DEMO_DIR",
    "Project",
    "ProjectNotFound",
    "find_project",
    "require_project",
    "demo_project",
]
