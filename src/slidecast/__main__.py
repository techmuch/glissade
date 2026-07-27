"""Allow `python -m slidecast` as well as the installed `slidecast` command."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
