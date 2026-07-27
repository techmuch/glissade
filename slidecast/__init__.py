"""Slidecast — a self-contained presentation server with a phone remote.

Serves a deck to a projector and a separate remote-control page to a phone on
the same Wi-Fi. Both stay in sync over server-sent events. Decks build to a
single HTML file with every image and activity embedded, so a presentation
still works with no network at all.
"""

from pathlib import Path

__version__ = "0.2.1"

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
DECKS_DIR = PROJECT_DIR / "decks"
THEMES_JSON = PROJECT_DIR / "themes.json"
BUILD_DIR = PROJECT_DIR / "build"
SETTINGS_JSON = PROJECT_DIR / "presenter-settings.json"

__all__ = [
    "PACKAGE_DIR",
    "PROJECT_DIR",
    "TEMPLATE_DIR",
    "DECKS_DIR",
    "THEMES_JSON",
    "BUILD_DIR",
    "SETTINGS_JSON",
]
