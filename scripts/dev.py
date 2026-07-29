#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PYTHON = "3.12"
DEFAULT_EXTRAS = "dev,images"


def uv() -> str:
    found = shutil.which("uv")
    if not found:
        raise SystemExit("uv is required. Install it from https://docs.astral.sh/uv/")
    return found


def venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def run(cmd: list[str], *, cwd: Path = ROOT) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def require_venv(venv: Path) -> Path:
    python = venv_python(venv)
    if not python.exists():
        raise SystemExit(
            f"{python} not found. Run `uv run python scripts/dev.py install` first."
        )
    return python


def cmd_install(args: argparse.Namespace) -> None:
    venv = ROOT / args.venv
    run([uv(), "python", "install", args.python])
    run([uv(), "venv", str(venv), "--python", args.python])
    run([
        uv(),
        "pip",
        "install",
        "--python",
        str(venv_python(venv)),
        "-e",
        f".[{args.extras}]",
    ])


def passthrough(argv: list[str]) -> list[str]:
    return argv[1:] if argv and argv[0] == "--" else argv


def cmd_test(args: argparse.Namespace) -> None:
    python = require_venv(ROOT / args.venv)
    extra = passthrough(args.args)
    cmd = [str(python), "-m", "pytest"]
    if not extra:
        cmd.append("-q")
    cmd.extend(extra)
    run(cmd)


def cmd_run(args: argparse.Namespace) -> None:
    python = require_venv(ROOT / args.venv)
    glissade_args = passthrough(args.args) or ["demo"]
    run([str(python), "-m", "glissade", *glissade_args])


def cmd_build(args: argparse.Namespace) -> None:
    run([uv(), "build", *passthrough(args.args)])


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Cross-platform developer tasks for Glissade."
    )
    sub = p.add_subparsers(dest="command", required=True)

    install = sub.add_parser(
        "install",
        help="Install Python if needed, create .venv, and install dev dependencies.",
    )
    install.add_argument(
        "--python",
        default=DEFAULT_PYTHON,
        help=f"Python version for the local venv (default: {DEFAULT_PYTHON})",
    )
    install.add_argument(
        "--venv",
        default=".venv",
        help="Virtualenv directory (default: .venv)",
    )
    install.add_argument(
        "--extras",
        default=DEFAULT_EXTRAS,
        help=f"Extras to install from the project (default: {DEFAULT_EXTRAS})",
    )
    install.set_defaults(func=cmd_install)

    test = sub.add_parser("test", help="Run pytest inside the local .venv.")
    test.add_argument(
        "--venv",
        default=".venv",
        help="Virtualenv directory (default: .venv)",
    )
    test.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to pytest",
    )
    test.set_defaults(func=cmd_test)

    run_p = sub.add_parser(
        "run",
        help="Run Glissade inside the local .venv. Defaults to `glissade demo`.",
    )
    run_p.add_argument(
        "--venv",
        default=".venv",
        help="Virtualenv directory (default: .venv)",
    )
    run_p.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to `python -m glissade`",
    )
    run_p.set_defaults(func=cmd_run)

    build = sub.add_parser(
        "build",
        help="Build distributable packages into dist/ using `uv build`.",
    )
    build.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to `uv build`",
    )
    build.set_defaults(func=cmd_build)

    return p


def main() -> int:
    args = parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
