"""The `slidecast` command.

    slidecast init      scaffold a project in the current directory
    slidecast start     present a deck, with a phone remote
    slidecast build     write standalone HTML for every deck
    slidecast check     validate decks
    slidecast decks     list what's here
    slidecast themes    list available themes
    slidecast demo      present the decks that ship with the tool
"""

from __future__ import annotations

import argparse
import shutil
import socket
import sys
from pathlib import Path

from . import __version__
from . import decks as deck_lib
from .project import (
    SCAFFOLD_DIR,
    SCHEMA_FILE,
    Project,
    ProjectNotFound,
    demo_project,
    require_project,
)
from .term import bold, dim, out, rule

# ---------------------------------------------------------------- helpers


def _project(args) -> Project:
    return require_project(Path(args.dir).resolve() if getattr(args, "dir", None) else None)


def _decks_or_die(project: Project, wanted: str | None = None) -> list[dict]:
    found = deck_lib.discover(project)
    if not found:
        raise SystemExit(
            f"No decks in {project.decks_dir}.\n"
            f"Add a .json file there, or run `slidecast init` to scaffold one."
        )
    if not wanted:
        return found
    chosen = [d for d in found if d["id"] == wanted]
    if not chosen:
        raise SystemExit(
            f"No deck called {wanted!r}. Available: " + ", ".join(d["id"] for d in found)
        )
    return chosen


def lan_ip() -> str:
    """Best guess at this machine's address on the local network.

    No packets are sent — connecting a UDP socket just asks the routing table
    which interface would reach the outside world.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def qr_lines(data: str) -> list[str]:
    try:
        import qrcode
    except ImportError:
        return []
    try:
        qr = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(data)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        lines = []
        for top in range(0, len(matrix), 2):
            row = ""
            for col in range(len(matrix[top])):
                upper = matrix[top][col]
                lower = matrix[top + 1][col] if top + 1 < len(matrix) else False
                row += {(0, 0): " ", (1, 0): "▀", (0, 1): "▄", (1, 1): "█"}[
                    (int(upper), int(lower))
                ]
            lines.append(row)
        return lines
    except Exception:
        return []


# ------------------------------------------------------------------ init


def cmd_init(args) -> int:
    target = Path(args.dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    planned: list[tuple[Path, Path]] = []
    for src in sorted(SCAFFOLD_DIR.rglob("*")):
        if src.is_dir():
            continue
        planned.append((src, target / src.relative_to(SCAFFOLD_DIR)))
    planned.append((SCHEMA_FILE, target / "slidecast.schema.json"))

    clashes = [dst for _, dst in planned if dst.exists()]
    if clashes and not args.force:
        out("Already here:")
        for c in clashes:
            out(f"  {c.relative_to(target)}")
        out("\nNothing written. Re-run with --force to overwrite.")
        return 1

    for src, dst in planned:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    out()
    out(f"  {bold('Slidecast project ready')}  {dim(str(target))}")
    out("  " + rule())
    for _, dst in planned:
        out(f"  {dst.relative_to(target)}")
    out()
    out("  Next:")
    out(f"    {bold('slidecast start')}    present it")
    out(f"    {bold('slidecast check')}    validate after editing")
    out()
    out(dim("  AGENTS.md is written for an AI assistant — point one at this"))
    out(dim("  directory and ask it to build your deck."))
    out()
    return 0


# ----------------------------------------------------------------- start


def cmd_start(args) -> int:
    import uvicorn

    from .app import create_app

    project = demo_project() if args._demo else _project(args)
    defaults = project.config()
    port = args.port or int(defaults.get("port", 8000))
    host = args.host or str(defaults.get("host", "0.0.0.0"))
    deck = args.deck or defaults.get("deck")

    app = create_app(project, deck)
    show = app.state.show
    current = next((d for d in app.state.decks if d["id"] == show.deck), None)

    ip = lan_ip() if host == "0.0.0.0" else host
    display = f"http://{ip}:{port}/"
    control = f"http://{ip}:{port}/control"

    out()
    out(f"  {bold('Slidecast')} {dim('v' + __version__)}")
    out("  " + rule())
    if current:
        out(f"  Deck     {bold(current['title'])}  ({len(current['slides'])} slides)")
    others = [d["id"] for d in app.state.decks if not current or d["id"] != current["id"]]
    if others:
        out(f"  Also     {', '.join(others)}   {dim('(switch from the remote)')}")
    out()
    out(f"  Slides   {dim('(projector)')}  {bold(display)}")
    out(f"  Remote   {dim('(your phone)')} {bold(control)}")
    if host == "0.0.0.0":
        out(f"  Also at  http://localhost:{port}/")
    out()

    for line in qr_lines(control):
        out("   " + line)
    if qr_lines(control):
        out()

    out("  Open the deck on the projecting machine and press F for fullscreen.")
    out(dim("  Ctrl-C to stop."))
    out()
    sys.stdout.flush()

    if args.open:
        import webbrowser

        webbrowser.open(f"http://127.0.0.1:{port}/")

    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except KeyboardInterrupt:  # pragma: no cover
        pass
    return 0


# ----------------------------------------------------------------- build


def cmd_build(args) -> int:
    from .build import build_all

    project = demo_project() if args._demo else _project(args)
    chosen = _decks_or_die(project, args.deck)
    if args.out:
        out_dir = Path(args.out).resolve()
    elif args._demo:
        # Never write into the installed package; the demo builds go where the
        # user actually is.
        out_dir = Path.cwd() / "build"
    else:
        out_dir = project.build_dir

    results = build_all(project, chosen, out_dir)
    remote: list[tuple] = []
    out()
    for r in results:
        try:
            shown = r.path.relative_to(Path.cwd())
        except ValueError:
            shown = r.path
        count = len(r.deck["slides"])
        out(f"  {bold(str(shown))}  " + dim(f"{count} slides, {r.size:,} bytes"))
        for w in r.warnings:
            out(f"    ! {w}")
        remote += [(r.deck["title"], n, url) for n, url in r.remote]

    if remote:
        out()
        out(f"  {len(remote)} embed(s) need live internet:")
        for title, n, url in remote:
            out(f"    {title} slide {n}: {url}")
        out(dim("  If the network is down these show a QR code fallback instead."))
    out()
    return 0


# ----------------------------------------------------------------- check


def cmd_check(args) -> int:
    from .check import check_deck

    project = demo_project() if args._demo else _project(args)
    chosen = _decks_or_die(project, args.deck)

    errors = warnings = 0
    out()
    for deck in chosen:
        issues = check_deck(deck)
        errs = [i for i in issues if i.level == "error"]
        warns = [i for i in issues if i.level == "warning"]
        errors += len(errs)
        warnings += len(warns)

        status = "OK" if not errs else f"{len(errs)} error(s)"
        count = len(deck["slides"])
        out(f"  {bold(deck['title'])}  " + dim(f"{count} slides") + f"  {status}")
        for i in errs:
            out(f"    error   {i}")
        if not args.quiet:
            for i in warns:
                out(f"    warn    {i}")

    out()
    if errors:
        out(f"  {errors} error(s), {warnings} warning(s)")
        return 1
    out(f"  No errors. {warnings} warning(s).")
    out()
    return 0


# ------------------------------------------------------------ list things


def cmd_decks(args) -> int:
    project = demo_project() if args._demo else _project(args)
    found = _decks_or_die(project)
    out()
    out(f"  {dim(str(project.decks_dir))}")
    for d in found:
        count = len(d["slides"])
        out(f"  {bold(d['id']):<24} {d['title']}  " + dim(f"({count} slides)"))
        if d.get("subtitle"):
            out(f"  {'':<22} {dim(d['subtitle'])}")
    out()
    return 0


def cmd_themes(args) -> int:
    from .app import load_themes

    try:
        project = _project(args)
    except (ProjectNotFound, SystemExit):
        project = None
    themes = load_themes(project)
    out()
    source = project.themes_file if project else "built in"
    out(f"  {dim(str(source))}")
    for t in themes:
        out(f"  {bold(t['id']):<24} {t.get('name', t['id'])}")
        if t.get("description"):
            out(f"  {'':<22} {dim(t['description'])}")
    out()
    return 0


# ------------------------------------------------------------------ main


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="slidecast",
        description="Presentation decks written as JSON, driven from your phone.",
    )
    p.add_argument("--version", action="version", version=f"slidecast {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    def common(sp):
        sp.add_argument(
            "-C", "--dir", default=None, metavar="PATH",
            help="run as if started in this directory",
        )
        sp.add_argument("--demo", dest="_demo", action="store_true",
                        help="use the decks that ship with slidecast")
        return sp

    sp = sub.add_parser("init", help="scaffold a project in a directory")
    sp.add_argument("dir", nargs="?", default=".", help="target directory (default: here)")
    sp.add_argument("-f", "--force", action="store_true", help="overwrite existing files")
    sp.set_defaults(func=cmd_init)

    sp = common(sub.add_parser("start", help="present a deck"))
    sp.add_argument("--deck", default=None, help="deck id to open with")
    sp.add_argument("--host", default=None,
                    help="bind address (default 0.0.0.0, so a phone can reach it)")
    sp.add_argument("--port", type=int, default=None, help="port (default 8000)")
    sp.add_argument("--open", action="store_true", help="open the deck in your browser")
    sp.set_defaults(func=cmd_start)

    sp = common(sub.add_parser("build", help="write standalone HTML"))
    sp.add_argument("deck", nargs="?", default=None, help="deck id (default: all)")
    sp.add_argument("-o", "--out", default=None, help="output directory (default: build/)")
    sp.set_defaults(func=cmd_build)

    sp = common(sub.add_parser("check", help="validate decks"))
    sp.add_argument("deck", nargs="?", default=None, help="deck id (default: all)")
    sp.add_argument("-q", "--quiet", action="store_true", help="errors only")
    sp.set_defaults(func=cmd_check)

    sp = common(sub.add_parser("decks", help="list decks"))
    sp.set_defaults(func=cmd_decks)

    sp = common(sub.add_parser("themes", help="list themes"))
    sp.set_defaults(func=cmd_themes)

    sp = sub.add_parser("demo", help="present the decks that ship with slidecast")
    sp.add_argument("--deck", default=None, help="tour or gallery")
    sp.add_argument("--host", default=None)
    sp.add_argument("--port", type=int, default=None)
    sp.add_argument("--open", action="store_true")
    sp.set_defaults(func=cmd_start, _demo=True, dir=None)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    if not hasattr(args, "_demo"):
        args._demo = False
    try:
        return args.func(args)
    except ProjectNotFound as exc:
        out(f"\n  {exc}\n")
        return 2
    except KeyboardInterrupt:  # pragma: no cover
        out()
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
