"""Terminal output that behaves on Windows too.

Windows 10+ consoles support ANSI, but only after virtual-terminal processing
is switched on, and older ones never do. Rather than guess, enable it where
possible and strip the codes where not — so the CLI never prints `\033[1m` at
someone.
"""

from __future__ import annotations

import os
import sys


def _supports_ansi() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if sys.platform != "win32":
        return True
    if os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM"):
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING on the stdout handle.
        return bool(kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7))
    except Exception:
        return False


ANSI = _supports_ansi()

_CODES = {"bold": "\033[1m", "dim": "\033[2m", "reset": "\033[0m"}


def bold(text: str) -> str:
    return f"{_CODES['bold']}{text}{_CODES['reset']}" if ANSI else text


def dim(text: str) -> str:
    return f"{_CODES['dim']}{text}{_CODES['reset']}" if ANSI else text


def rule(width: int = 46) -> str:
    """Box-drawing characters need a console that can encode them."""
    ch = "─"
    try:
        ch.encode(sys.stdout.encoding or "utf-8")
    except (UnicodeEncodeError, LookupError):
        ch = "-"
    return ch * width


def out(text: str = "") -> None:
    """Print, tolerating consoles that can't encode what we'd like to say."""
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(text.encode(enc, "replace").decode(enc))
