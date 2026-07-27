"""Allow `python -m glissade` as well as the installed `glissade` command."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
