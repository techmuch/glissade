"""Keeping a project's tool-owned files current.

`init` writes two kinds of file. Some belong to Glissade and should track the
installed release — AGENTS.md describes the deck format, and the schema copy is
what your editor validates against, so both go stale the moment you upgrade.
The rest are yours from the moment they land: your decks, your config, your
.gitignore.

`update` refreshes the first kind and never touches the second. To tell an
untouched file from one you've edited, init and update record a hash of what
they wrote; a file that still matches can be replaced freely, and one that
doesn't is backed up rather than thrown away.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .project import SCAFFOLD_DIR, SCHEMA_FILE, Project

# Tracks the installed release; refreshed by `update`.
OWNED = ("AGENTS.md", "glissade.schema.json")

# Written once by `init`; yours thereafter. Never rewritten, because these are
# where the work lives.
YOURS = ("decks/", "themes.json", "glissade.toml", ".gitignore")

MANIFEST_VERSION = 1


def _hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def source_for(name: str) -> Path:
    """Where a tool-owned file comes from."""
    if name == "glissade.schema.json":
        return SCHEMA_FILE
    return SCAFFOLD_DIR / name


def manifest_path(project: Project) -> Path:
    return project.state_dir / "scaffold.json"


def read_manifest(project: Project) -> dict:
    try:
        with manifest_path(project).open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_manifest(project: Project, files: dict[str, str], created: str | None = None) -> None:
    """Record what we wrote, so a later update knows what it may replace."""
    existing = read_manifest(project)
    payload = {
        "manifest": MANIFEST_VERSION,
        "created_with": created or existing.get("created_with") or __version__,
        "updated_with": __version__,
        "files": {**existing.get("files", {}), **files},
    }
    try:
        manifest_path(project).parent.mkdir(parents=True, exist_ok=True)
        manifest_path(project).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
    except OSError:
        pass


@dataclass
class Change:
    name: str
    action: str      # "current" | "update" | "create" | "edited"
    target: Path
    source: Path

    @property
    def needs_write(self) -> bool:
        return self.action in ("update", "create", "edited")


def plan(project: Project) -> list[Change]:
    """Work out what `update` would do, without doing any of it."""
    recorded = read_manifest(project).get("files", {})
    changes: list[Change] = []
    for name in OWNED:
        target = project.root / name
        source = source_for(name)
        if not target.exists():
            changes.append(Change(name, "create", target, source))
            continue
        current = _hash(target)
        if current == _hash(source):
            changes.append(Change(name, "current", target, source))
        elif recorded.get(name) and recorded[name] != current:
            # Differs from the shipped copy *and* from what we last wrote:
            # the difference is the user's, so it is not ours to discard.
            changes.append(Change(name, "edited", target, source))
        else:
            changes.append(Change(name, "update", target, source))
    return changes


def apply(project: Project, changes: list[Change], keep_edits: bool = False) -> list[str]:
    """Carry out a plan. Returns a line per file for the CLI to print."""
    written: dict[str, str] = {}
    notes: list[str] = []

    for change in changes:
        if change.action == "current":
            notes.append(f"current   {change.name}")
            continue
        if change.action == "edited":
            if keep_edits:
                notes.append(f"kept      {change.name} (yours; --keep)")
                continue
            backup = change.target.with_suffix(change.target.suffix + ".bak")
            try:
                shutil.copyfile(change.target, backup)
            except OSError:
                notes.append(f"skipped   {change.name} (couldn't back it up)")
                continue
            shutil.copyfile(change.source, change.target)
            written[change.name] = _hash(change.target)
            notes.append(f"updated   {change.name}  (yours saved as {backup.name})")
            continue

        change.target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(change.source, change.target)
        written[change.name] = _hash(change.target)
        notes.append(f"{'created' if change.action == 'create' else 'updated'}   {change.name}")

    if written:
        write_manifest(project, written)
    return notes


def record_init(project: Project, names: list[str]) -> None:
    """Called by `init` so the first update knows what it inherited."""
    files = {
        name: _hash(project.root / name)
        for name in names
        if (project.root / name).is_file()
    }
    write_manifest(project, files, created=__version__)
