"""Build decks into standalone HTML files.

    pixi run build              # every deck in decks/
    pixi run build tour         # just one

Each output is the offline fallback — no server, no network, just open it in a
browser. It is built from the same template the server uses, so the two can't
drift apart. Local images and activities are inlined, so the single file
carries everything with it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import BUILD_DIR
from . import decks as deck_lib
from .app import load_themes, prepared_slides, render_deck
from .assets import external_media


def build_one(deck: dict, out_dir: Path, themes: list) -> tuple[Path, list[str], list]:
    slides, warnings = prepared_slides(deck)
    html = render_deck(slides, live=False, themes=themes, title=deck["title"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{deck['id']}.html"
    out.write_text(html, encoding="utf-8")
    return out, warnings, external_media(slides)


def main() -> None:
    p = argparse.ArgumentParser(prog="slidecast.build", description=__doc__)
    p.add_argument("deck", nargs="?", default=None, help="deck id (default: all)")
    p.add_argument("-o", "--out", default=str(BUILD_DIR), help="output directory")
    args = p.parse_args()

    all_decks = deck_lib.discover()
    if not all_decks:
        raise SystemExit("No decks found. Add a .json file to decks/.")

    chosen = (
        [d for d in all_decks if d["id"] == args.deck] if args.deck else all_decks
    )
    if not chosen:
        raise SystemExit(
            f"No deck called {args.deck!r}. Available: "
            + ", ".join(d["id"] for d in all_decks)
        )

    themes = load_themes()
    out_dir = Path(args.out).resolve()
    remote_all: list[tuple] = []

    for deck in chosen:
        out, warnings, remote = build_one(deck, out_dir, themes)
        size = out.stat().st_size
        print(f"{out.relative_to(Path.cwd()) if out.is_relative_to(Path.cwd()) else out}"
              f"  —  {len(deck['slides'])} slides, {size:,} bytes")
        for w in warnings:
            print(f"  ! {w}")
        remote_all += [(deck["title"], n, url) for n, url in remote]

    # The decks are otherwise fully self-contained, so anything still reaching
    # for the network is worth naming before you're standing in front of a room.
    if remote_all:
        print(f"\n  {len(remote_all)} embed(s) need live internet:")
        for title, n, url in remote_all:
            print(f"    {title} slide {n}: {url}")
        print("  If the Wi-Fi is down these show a QR code fallback instead.")


if __name__ == "__main__":
    main()
