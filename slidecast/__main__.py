"""Entry point: `pixi run start`.

Prints the two addresses you need — the deck for the projector, the remote for
your phone — plus a QR code so you don't have to type a URL on a phone keyboard
while standing in front of a room.
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

import uvicorn

from .app import create_app


def lan_ip() -> str:
    """Best guess at this machine's address on the local network.

    No packets are actually sent — connecting a UDP socket just asks the
    routing table which interface would be used to reach the outside world.
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
    """Render a QR code as text, if the optional `qrcode` package is present."""
    try:
        import qrcode  # type: ignore
    except ImportError:
        return []

    qr = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()

    # Two vertical modules per character cell using half-block glyphs, so the
    # code stays square in a terminal.
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


def banner(host: str, port: int, deck=None, decks=None) -> None:
    ip = lan_ip() if host == "0.0.0.0" else host
    display = f"http://{ip}:{port}/"
    control = f"http://{ip}:{port}/control"

    print()
    print("  \033[1mSlidecast\033[0m")
    print("  " + "─" * 46)
    if deck:
        print(f"  Deck     \033[1m{deck['title']}\033[0m  ({len(deck['slides'])} slides)")
    if decks and len(decks) > 1:
        others = ", ".join(d["id"] for d in decks if not deck or d["id"] != deck["id"])
        print(f"  Also     {others}   (switch from the remote)")
    print()
    print(f"  Slides   (projector)  \033[1m{display}\033[0m")
    print(f"  Remote   (your phone) \033[1m{control}\033[0m")
    if host == "0.0.0.0":
        print(f"  Also at  http://localhost:{port}/")
    print()

    lines = qr_lines(control)
    if lines:
        print("  Scan for the remote:")
        for line in lines:
            print("   " + line)
        print()
    print("  Open the deck on the projecting machine and press F for fullscreen.")
    print("  Ctrl-C to stop.")
    print()
    # stdout is block-buffered when piped to a file or another process, which
    # would otherwise hide these addresses until the server exits.
    sys.stdout.flush()


def main() -> None:
    p = argparse.ArgumentParser(prog="slidecast", description=__doc__)
    p.add_argument(
        "--host",
        default="0.0.0.0",
        help="bind address; defaults to 0.0.0.0 so a phone on the same Wi-Fi can reach it",
    )
    p.add_argument("--port", type=int, default=8000, help="port (default: 8000)")
    p.add_argument(
        "--deck",
        default=None,
        help="deck id to open with (default: whichever was used last)",
    )
    args = p.parse_args()

    app = create_app(args.deck)
    show = app.state.show
    current = next((d for d in app.state.decks if d["id"] == show.deck), None)

    banner(args.host, args.port, current, app.state.decks)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
