"""The `glissade` command.

    glissade init      scaffold a project in the current directory
    glissade start     present a deck, with a phone remote
    glissade build     write standalone HTML for every deck
    glissade check     validate decks
    glissade decks     list what's here
    glissade themes    list available themes
    glissade demo      present the decks that ship with the tool
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
            f"Add a .json file there, or run `glissade init` to scaffold one."
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
    planned.append((SCHEMA_FILE, target / "glissade.schema.json"))

    # --force refreshes the scaffold; it must never reach a deck. Losing an
    # afternoon's writing to a command meant to refresh a doc is not a trade
    # anyone would accept.
    from .scaffold import YOURS, record_init

    def is_yours(dst: Path) -> bool:
        rel = dst.relative_to(target).as_posix()
        return any(rel.startswith(y) if y.endswith("/") else rel == y for y in YOURS)

    if args.force:
        protected = [dst for _, dst in planned if dst.exists() and is_yours(dst)]
        planned = [(src, dst) for src, dst in planned
                   if not (dst.exists() and is_yours(dst))]
        if protected:
            out()
            out("  Keeping what's already yours:")
            for dst in protected:
                out(f"    {dst.relative_to(target)}")

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
    record_init(Project(target), [dst.relative_to(target).as_posix() for _, dst in planned])

    out()
    out(f"  {bold('Glissade project ready')}  {dim(str(target))}")
    out("  " + rule())
    for _, dst in planned:
        out(f"  {dst.relative_to(target)}")
    out()
    if not planned:
        out(dim("  Nothing to write — everything here is already yours."))
    out()
    out("  Next:")
    out(f"    {bold('glissade start')}    present it")
    out(f"    {bold('glissade check')}    validate after editing")
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
    _warn_if_deck_needs_newer(app.state.decks)
    show = app.state.show
    current = next((d for d in app.state.decks if d["id"] == show.deck), None)

    ip = lan_ip() if host == "0.0.0.0" else host
    display = f"http://{ip}:{port}/"
    control = f"http://{ip}:{port}/control"

    out()
    out(f"  {bold('Glissade')} {dim('v' + __version__)}")
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

    # Built by hand rather than uvicorn.run() so the app can reach the server
    # and see its shutdown flag; the event stream watches it to end itself.
    # timeout_graceful_shutdown is the backstop for anything else that might
    # still be holding a connection open.
    config = uvicorn.Config(
        app, host=host, port=port, log_level="warning", timeout_graceful_shutdown=5
    )
    server = uvicorn.Server(config)
    app.state.server = server

    try:
        server.run()
    except KeyboardInterrupt:  # pragma: no cover - a second Ctrl-C
        pass
    out(dim("  Stopped."))
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

    _warn_if_deck_needs_newer(chosen)
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

    if args.fix:
        from .fix import apply as apply_fixes

        applied = []
        for deck in chosen:
            for f in apply_fixes(Path(deck["path"])):
                applied.append((deck["id"], f))
        out()
        if applied:
            out(f"  Fixed {len(applied)}:")
            for deck_id, f in applied:
                out(f"    [{deck_id}] {f}")
            out(dim("    Originals kept as <deck>.json.bak"))
            # Re-read so the report below reflects the corrected files.
            chosen = _decks_or_die(project, args.deck)
        else:
            out(dim("  Nothing to fix automatically."))

    errors = warnings = 0
    out()
    if not args._demo:
        _warn_if_schema_stale(project)
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


def _warn_if_deck_needs_newer(decks: list[dict]) -> None:
    """Say so before presenting, but still present.

    Refusing to start would be the wrong trade in a room with an audience in
    it — a deck that renders most of itself beats a deck that renders none.
    """
    from .upgrade import BadRequirement, satisfies

    for deck in decks:
        req = deck.get("requires")
        if not req:
            continue
        try:
            if satisfies(__version__, str(req)):
                continue
        except BadRequirement:
            out(dim(f"  ! {deck['id']}: can't read its `glissade` requirement {req!r}"))
            continue
        out(f"  ! {bold(deck['title'])} asks for Glissade {req}; this is {__version__}.")
        out(dim("    Anything newer than this release won't render. `glissade upgrade`"))
        out()


def _warn_if_schema_stale(project: Project) -> None:
    """A project's schema copy is frozen at init; the editor reads that copy."""
    local = project.root / "glissade.schema.json"
    if not local.is_file():
        return
    try:
        import json as _json

        theirs = _json.loads(local.read_text(encoding="utf-8"))
        ours = _json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if theirs.get("x-glissade-version") != ours.get("x-glissade-version"):
        out(f"  ! glissade.schema.json was written by "
            f"{theirs.get('x-glissade-version', 'an older release')}; "
            f"this is {ours.get('x-glissade-version', __version__)}.")
        out(dim("    Your editor validates against that copy. Run `glissade schema`."))
        out()


def cmd_update(args) -> int:
    """Bring a project's tool-owned files up to the installed release."""
    from .scaffold import apply, plan, read_manifest

    project = _project(args)
    manifest = read_manifest(project)
    changes = plan(project)

    out()
    out(f"  {bold(str(project.root))}")
    created = manifest.get("created_with")
    updated = manifest.get("updated_with")
    if created:
        seen = f"created with v{created}"
        if updated and updated != created:
            seen += f", last updated with v{updated}"
        out(dim(f"  {seen}; installed is v{__version__}"))
    else:
        out(dim(f"  no record of which release made this; installed is v{__version__}"))
    out()

    pending = [c for c in changes if c.needs_write]
    if not pending:
        out("  Everything Glissade owns here is already current.")
        out(dim("  Your decks, themes and config are never touched by this command."))
        out()
        return 0

    if args.dry_run:
        out("  Would change:")
        for c in pending:
            note = "  (you edited this — a .bak would be kept)" if c.action == "edited" else ""
            out(f"    {c.action:<8}  {c.name}{dim(note)}")
        out()
        out(dim("  Run without --dry-run to apply."))
        out()
        return 0

    for line in apply(project, changes, keep_edits=args.keep):
        out(f"  {line}")
    out()
    out(dim("  Decks, themes and config were not touched."))
    out()
    return 0


def cmd_schema(args) -> int:
    """Refresh the project's copy of the JSON schema."""
    project = _project(args)
    target = project.root / "glissade.schema.json"
    existed = target.is_file()
    shutil.copyfile(SCHEMA_FILE, target)
    out()
    out(f"  {'Updated' if existed else 'Wrote'} {bold(str(target.relative_to(project.root)))}")
    out(dim(f"  Schema v{_schema_stamp()} — editors validating against it are current again."))
    out()
    return 0


def _schema_stamp() -> str:
    try:
        import json as _json

        return str(_json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
                   .get("x-glissade-version", __version__))
    except (OSError, ValueError):  # pragma: no cover
        return __version__


# --------------------------------------------------------------- upgrade


def cmd_upgrade(args) -> int:
    from .upgrade import (
        NOT_PUBLISHED,
        detect_installer,
        is_newer,
        latest_version,
        run_upgrade,
    )

    installer = detect_installer()
    out()
    out(f"  Installed {bold('v' + __version__)} via {bold(installer.kind)}")
    if installer.note:
        out(dim(f"  {installer.note}"))

    out(dim("  Checking PyPI…"))
    latest, why = latest_version()
    if latest is None:
        out()
        if why == NOT_PUBLISHED:
            out(f"  PyPI has no releases of {bold('glissade')} yet, so there's nothing to")
            out("  upgrade to. You're running a build installed from source.")
        else:
            out("  Couldn't reach PyPI. Check your connection, or upgrade directly:")
            out(f"    {bold(installer.printable)}")
        out()
        return 1

    if not is_newer(latest, __version__):
        out(f"  Latest is {bold('v' + latest)} — you're up to date.")
        out()
        return 0

    out(f"  {bold('v' + latest)} is available.")
    out()

    if args.check:
        out(f"  To upgrade:  {bold(installer.printable)}")
        out()
        return 0

    if not installer.runnable:
        out(f"  {installer.command[0]!r} isn't on your PATH. Run this yourself:")
        out(f"    {bold(installer.printable)}")
        out()
        return 1

    out(f"  Running: {dim(installer.printable)}")
    out()
    # Glissade never rewrites its own files — a running process can't safely
    # replace them, and on Windows the console script is locked outright.
    code = run_upgrade(installer)
    out()
    if code == 0:
        out(f"  Upgraded. Run {bold('glissade --version')} to confirm.")
    else:
        out(f"  The upgrade command exited {code}. Try running it yourself:")
        out(f"    {bold(installer.printable)}")
    out()
    return code


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
        prog="glissade",
        description="Presentation decks written as JSON, driven from your phone.",
    )
    p.add_argument("--version", action="version", version=f"glissade {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    def common(sp):
        sp.add_argument(
            "-C", "--dir", default=None, metavar="PATH",
            help="run as if started in this directory",
        )
        sp.add_argument("--demo", dest="_demo", action="store_true",
                        help="use the decks that ship with glissade")
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
    sp.add_argument("--fix", action="store_true",
                    help="apply the corrections that have one obvious answer")
    sp.set_defaults(func=cmd_check)

    sp = common(sub.add_parser("decks", help="list decks"))
    sp.set_defaults(func=cmd_decks)

    sp = common(sub.add_parser("themes", help="list themes"))
    sp.set_defaults(func=cmd_themes)

    sp = common(sub.add_parser(
        "update", help="bring this project's Glissade-owned files up to date"))
    sp.add_argument("--dry-run", action="store_true", help="show what would change")
    sp.add_argument("--keep", action="store_true",
                    help="leave files you've edited alone instead of backing them up")
    sp.set_defaults(func=cmd_update)

    sp = common(sub.add_parser("schema", help="refresh the project's JSON schema copy"))
    sp.set_defaults(func=cmd_schema)

    sp = sub.add_parser("upgrade", help="update glissade to the latest release")
    sp.add_argument(
        "--check", action="store_true",
        help="only report whether a newer version exists",
    )
    sp.set_defaults(func=cmd_upgrade)

    sp = sub.add_parser("demo", help="present the decks that ship with glissade")
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
