"""Upgrading Glissade.

A running process cannot safely replace its own files — on Windows the console
script is locked while it executes — so Glissade never rewrites itself. It
works out how it was installed and hands the job to that installer.

Nothing here runs unless you ask for it. A presentation tool that reaches the
network on its own can stall or print a notice at exactly the wrong moment, so
there is no background check and no startup ping.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PACKAGE = "glissade"
PYPI_URL = f"https://pypi.org/pypi/{PACKAGE}/json"


@dataclass(frozen=True)
class Installer:
    """How this copy of Glissade got here, and how to update it."""

    kind: str            # "uv" | "pipx" | "pip" | "unknown"
    command: list[str]
    note: str = ""

    @property
    def printable(self) -> str:
        return " ".join(self.command)

    @property
    def runnable(self) -> bool:
        return bool(self.command) and shutil.which(self.command[0]) is not None


def detect_installer() -> Installer:
    """Work out which tool owns this install.

    uv and pipx each put their tool environments in a predictable place, so the
    interpreter's own prefix identifies them. Anything else is some flavour of
    pip, and the safest pip invocation is the one bound to this very
    interpreter — `sys.executable -m pip` — which upgrades the environment
    Glissade is actually installed in rather than whichever pip is on PATH.
    """
    # Split on both separators rather than trusting pathlib's, so a Windows
    # prefix is read correctly no matter which platform's Path class is in
    # play — detection shouldn't depend on where it happens to run.
    parts = [seg.lower() for seg in re.split(r"[\\/]+", str(Path(sys.prefix))) if seg]

    # .../uv/tools/glissade
    if "uv" in parts and "tools" in parts:
        return Installer("uv", ["uv", "tool", "upgrade", PACKAGE])

    # .../pipx/venvs/glissade
    if "pipx" in parts and "venvs" in parts:
        return Installer("pipx", ["pipx", "upgrade", PACKAGE])

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE]
    note = ""
    if _is_user_site():
        cmd.insert(-1, "--user")
        note = "installed for your user account"
    elif not _in_virtualenv():
        note = (
            "this looks like a system Python; consider `uv tool install glissade` "
            "or `pipx install glissade` so upgrades don't need admin rights"
        )
    return Installer("pip", cmd, note)


def _in_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _is_user_site() -> bool:
    try:
        import site

        user = site.getusersitepackages()
    except Exception:
        return False
    here = str(Path(__file__).resolve())
    return bool(user) and here.startswith(str(Path(user).resolve()))


# Why a lookup failed, so the message can say something true. "No such
# package" and "no network" are very different problems for the reader.
UNREACHABLE = "unreachable"
NOT_PUBLISHED = "not-published"


def latest_version(timeout: float = 10.0) -> tuple[str | None, str]:
    """Ask PyPI what the newest release is.

    Returns the version and an empty reason, or None and why not.
    """
    try:
        req = urllib.request.Request(
            PYPI_URL, headers={"Accept": "application/json", "User-Agent": f"{PACKAGE}-cli"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)["info"]["version"], ""
    except urllib.error.HTTPError as exc:
        return None, NOT_PUBLISHED if exc.code == 404 else UNREACHABLE
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None, UNREACHABLE


def parse_version(text: str) -> tuple:
    """Compare releases without pulling in a dependency.

    Only the numeric release segment is compared; a pre-release suffix sorts
    below the same numbers, which is enough to answer "is there something
    newer" for a tool versioned like this one.
    """
    head = text.strip()
    for sep in ("+", "-"):
        head = head.split(sep, 1)[0]
    numbers: list[int] = []
    tail = ""
    for chunk in head.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                tail = chunk[len(digits):]
                break
        numbers.append(int(digits) if digits else 0)
        if tail:
            break
    while len(numbers) < 3:
        numbers.append(0)
    return (tuple(numbers[:3]), 0 if tail else 1)


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


# A deck may declare the version it needs, e.g. ">=0.6" or ">=0.6,<1.0".
# Parsed here rather than pulling in packaging(), because the whole point of
# the dependency list is that installing Glissade can never fail.
_OPERATORS = ("<=", ">=", "==", "!=", "<", ">")


class BadRequirement(ValueError):
    """The requirement string isn't something we can read."""


def satisfies(version: str, requirement: str) -> bool:
    """True if `version` meets every clause of `requirement`.

    A bare version means "at least this", which is what people mean when
    they write "0.6" — the alternative reading, exact equality, would break
    every deck on the next release.
    """
    clauses = [c.strip() for c in str(requirement).split(",") if c.strip()]
    if not clauses:
        raise BadRequirement("empty requirement")

    have = parse_version(version)
    for clause in clauses:
        op = next((o for o in _OPERATORS if clause.startswith(o)), None)
        wanted = clause[len(op):].strip() if op else clause
        if not wanted or not wanted[0].isdigit():
            raise BadRequirement(f"can't read {clause!r}")
        want = parse_version(wanted)
        ok = {
            None: have >= want,
            ">=": have >= want,
            ">": have > want,
            "==": have == want,
            "!=": have != want,
            "<=": have <= want,
            "<": have < want,
        }[op]
        if not ok:
            return False
    return True


def run_upgrade(installer: Installer) -> int:
    """Hand off to the installer. Its output is the user's feedback."""
    env = dict(os.environ)
    return subprocess.call(installer.command, env=env)
