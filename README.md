# Glissade

Presentation decks written as JSON, driven from your phone, and built into a
single HTML file that works when the Wi-Fi doesn't.

```bash
uv tool install --from git+https://github.com/techmuch/glissade glissade

mkdir my-talk && cd my-talk
glissade init                # scaffold a deck and an AI-agent guide
glissade start               # present — prints a QR code for the remote
```

No project yet? `glissade demo` runs the decks that ship with the tool from
anywhere, and they document the whole system.

## Installing

Glissade is not on PyPI yet, so install it from GitHub for now.

| | |
| --- | --- |
| **uv** (recommended) | `uv tool install --from git+https://github.com/techmuch/glissade glissade` — installs Python too if you don't have it |
| **pipx** | `pipx install git+https://github.com/techmuch/glissade.git` |
| **pip** | `pip install git+https://github.com/techmuch/glissade.git` |
| **Try without installing** | `uvx --from git+https://github.com/techmuch/glissade glissade demo` |

One universal wheel covers Windows, macOS and Linux — every dependency is pure
Python, so installation never needs a compiler. Python 3.10 or newer.

If you want Pillow for image downscaling, install the `images` extra from Git
instead, for example:

```bash
pip install 'git+https://github.com/techmuch/glissade.git#egg=glissade[images]'
```

Without Pillow, images embed at full size; nothing breaks.

## Commands

| Command | Does |
| --- | --- |
| `glissade init [dir]` | Scaffold a project: a starter deck, `AGENTS.md`, and the JSON schema |
| `glissade start` | Present, with a phone remote on the same Wi-Fi |
| `glissade build [deck]` | Write standalone HTML to `build/` |
| `glissade check [deck]` | Validate decks — `--fix` applies the obvious corrections |
| `glissade decks` / `themes` | List what's available |
| `glissade demo` | Present the built-in tour and layout gallery |
| `glissade update` | Bring a project's Glissade-owned files up to date |
| `glissade schema` | Refresh the project's JSON schema copy |
| `glissade upgrade` | Update to the latest release |

Every command takes `-C PATH` to run as if started elsewhere. Commands find
your project by walking up from the working directory, the way git does, so
they work from any subdirectory.

### Versions and compatibility

A deck can declare the release it needs:

```jsonc
{
  "glissade": ">=0.6",
  "title": "My talk",
  "slides": [ ... ]
}
```

Ranges work too (`">=0.6,<1.0"`), and a bare `"0.6"` means *at least* 0.6.

Older releases don't fail silently on it. `glissade check` treats an unmet
requirement as an error, and `start` and `build` print a warning but still run
— a deck that renders most of itself beats one that refuses in front of an
audience.

The same applies to fields. Anything this release doesn't recognise is
reported rather than quietly ignored:

```
warn  slide 1: 'transition' isn't a field Glissade 0.6.0 understands — it will be ignored
        If the deck was written for a newer release, run `glissade upgrade`.
```

`init` copies the schema into your project, and your editor validates against
that copy — so it goes stale when you upgrade. `check` notices and tells you to
run `glissade schema`, which refreshes it.

### Fixing decks

`glissade check --fix` applies the corrections that have one obviously correct
answer:

```
Fixed 3:
  [talk] deck: record the deck format  'absent' -> '1'
  [talk] slide 4: correct the layout name  'media-rite' -> 'media-right'
  [talk] slide 9: use the YouTube embed URL  '…watch?v=ID' -> '…/embed/ID'
  Originals kept as <deck>.json.bak
```

That's the whole list: layout and modifier names that are unmistakably typos,
YouTube watch links, and the format stamp. It deliberately will **not** rename
an unrecognised field — the nearest spelling is often the wrong meaning
(`subtitle` looks closer to `title` than to `subheading`), and a field this
release doesn't know may belong to a newer one. Those stay reported.

Decks are never rewritten without `--fix`, and the original is kept as
`<deck>.json.bak`.

### The format stamp

A deck records the format it was written against:

```jsonc
{ "format": 1, "title": "My talk", "slides": [ ... ] }
```

Absent means 1. It exists so a future release can migrate a file rather than
guess at its age. `init` writes it, and `check --fix` adds it to older decks.

Distinct from `"glissade": ">=0.6"`, which is a *requirement* — what the deck
needs from the tool, rather than what the tool should assume about the deck.

### Upgrading a project

Upgrading the tool doesn't touch your projects. Two files in a project belong
to Glissade and track the release — `AGENTS.md`, which describes the deck
format, and `glissade.schema.json`, which your editor validates against. Both
go stale when you upgrade:

```bash
glissade update --dry-run   # what would change
glissade update             # refresh them
```

It refreshes only those two. Your decks, `themes.json`, `glissade.toml` and
`.gitignore` are yours from the moment `init` writes them and are never
rewritten.

If you've edited a Glissade-owned file — house rules appended to `AGENTS.md`,
say — it isn't discarded. `update` saves yours as `AGENTS.md.bak` and tells
you, or use `--keep` to leave it alone entirely. It knows the difference
because `init` and `update` record a hash of what they wrote, in
`.glissade/scaffold.json`, which also records the release the project was
created with.

`init --force` refreshes the scaffold too, but it will not overwrite anything
under `decks/` or your config — it lists what it kept.

### Upgrading Glissade

```bash
glissade upgrade           # check, then update
glissade upgrade --check   # just tell me if there's a newer one
```

It works out how Glissade was installed — uv, pipx, or pip — and runs that
tool's upgrade command, showing you the command first. It never rewrites its
own files: a running process can't safely replace them, and on Windows the
console script is locked outright. If the installer isn't on your PATH it
prints the command instead of guessing.

**Glissade only reaches the network when you run this command.** There's no
startup check and no background ping. It's a tool you run in front of an
audience; it shouldn't stall or print a notice at the wrong moment.

## A project

```
my-talk/
├── decks/
│   ├── talk.json          your deck
│   └── media/             images and activities it references
├── AGENTS.md              guide for an AI assistant writing slides
├── glissade.schema.json   editor autocomplete and validation
├── glissade.toml          optional defaults (deck, port, host)
├── themes.json            optional — overrides the built-in themes
├── .glissade/             generated presenter state and live notes
└── build/                 generated; rebuild any time
```

Only `decks/` is required. A directory containing it is a project.

## Writing decks with an AI assistant

`glissade init` writes an `AGENTS.md` alongside your deck: the full field
reference, the layout catalogue, worked examples, and the rules that matter
(every slide needs speaker notes; media paths are relative to the deck; use
`/embed/` YouTube URLs). Point Claude Code, Cursor, or any agent at the
directory and ask it to build your talk.

The loop that makes this work is `glissade check`. It validates structure and
the things a schema can't — missing image files, layouts that are near-miss
typos, grids with one image, YouTube watch links — and exits non-zero so an
agent knows it isn't done:

```
  error   slide 3: unknown layout 'media-rite'
            Did you mean 'media-right'?
  error   slide 7: image not found: media/chart.png
  error   slide 9: YouTube watch link will not embed
            Use the /embed/ form: https://www.youtube.com/embed/VIDEO_ID
```

## Presenting

`glissade start` prints two addresses and a QR code:

| Address | Open it on |
| --- | --- |
| `http://<your-ip>:8000/` | the machine driving the projector — press **F** for fullscreen |
| `http://<your-ip>:8000/control` | your phone (scan the QR) |

Both devices need to be on the same Wi-Fi. The server holds the slide
position, so whoever advances — phone or laptop — everyone follows, and a
device that reconnects lands on the right slide.

The remote also has a **Live notes** editor for capturing feedback or action
items during the meeting. Those notes autosave per slide and can optionally be
shown on the projector as an overlay. The overlay is plain text: line breaks
are preserved, and the projector toggles it with <kbd>L</kbd>.

`glissade start --open` opens the deck in your browser once the server is
actually accepting connections — put `open = true` in `glissade.toml` to make
that a project's default.

On Windows the first run may raise a firewall prompt: allow private networks
so your phone can reach the remote. `--host 127.0.0.1` avoids it if you only
want the laptop.

### The remote

The main view holds what you read while presenting — the current slide's
speaker notes, a preview of the next one, and capturing audience feedback as you go. A **Notes** drawer shows every captured
live note across the deck and jumps back to that slide when you tap an entry.
Everything else sits behind a header button: **Deck**, **Slides** (jump list),
**Notes** (captured live notes), and a gear for text size and theme. **Blank**
blacks out the projector.

Live notes are saved automatically to `.glissade/live-notes.json` in a normal
project. For the built-in demo decks, which live in the installed package,
Glissade keeps them in your user cache instead.

### Keys on the projecting machine

| Key | Does |
| --- | --- |
| <kbd>←</kbd> <kbd>→</kbd> | navigate |
| <kbd>N</kbd> | speaker notes on screen |
| <kbd>L</kbd> | toggle the live-notes overlay |
| <kbd>B</kbd> | blank the screen |
| <kbd>+</kbd> <kbd>−</kbd> <kbd>0</kbd> | text size (70–160%) |
| <kbd>T</kbd> | cycle theme |
| <kbd>R</kbd> | reload a failed embed |
| <kbd>F</kbd> | fullscreen |

## Writing a slide

Pick a `layout` and fill the fields it uses. Nothing is required.

```jsonc
{
  "title": "My talk",
  "slides": [
    {
      "title": "Growth came from one region",   // label in the jump list
      "layout": "media-right",
      "eyebrow": "Results",
      "heading": "Growth came from one region",
      "body": "<p>Everything else held flat.</p>",
      "image": { "src": "media/q3.png", "alt": "Bar chart", "fit": "contain" },
      "notes": "Don't read the chart aloud. Say the sentence and let them look."
    }
  ]
}
```

Layouts: `title`, `title-content`, `section`, `title-only`, `two-content`,
`comparison`, `content-caption`, `picture-caption`, `media-right`,
`media-left`, `media-full`, `media-caption`, `grid`, `quad-chart`, `blank`.

`cls` adds modifiers independent of layout: `"ask"` (dark, for questions),
`"story"`, `"center"`.

Run `glissade demo --deck gallery` to see all fifteen.

## Media

**Images embed, they don't link.** Point `src` at a file beside your deck; the
build inlines it as a data URI, downscaling anything over 2560px. The result is
one file with no folder to forget.

**Embeds** come in three kinds:

| Field | Behaviour | Needs network |
| --- | --- | --- |
| `"file": "media/game.html"` | Local HTML inlined as the iframe's `srcdoc` | No |
| `"srcdoc": "<html>…"` | Inline markup | No |
| `"src": "https://…"` | External page | **Yes** |

Embeds mount only while their slide is on screen — otherwise a video keeps
playing, audibly, after you've moved on. An external embed that can't load
shows a QR-code fallback rather than a blank frame; <kbd>R</kbd> retries.
`glissade build` lists every slide that depends on the network.

## Themes

**Paper** (default), **Georgia Tech**, and **Texas A&M** ship with the tool.
Press <kbd>T</kbd> or pick one on the remote.

Drop a `themes.json` in your project to replace them with your own. Every
colour and typeface in the deck comes from a token, so one entry restyles
everything:

```jsonc
{
  "id": "housestyle",
  "name": "House style",
  "vars": {
    "--paper": "#ffffff",        // slide background
    "--ink": "#111111",          // headings
    "--ink-soft": "#444444",     // body
    "--accent": "#8a6d2f",       // eyebrows, citations
    "--accent-light": "#c0a878", // quote bars, bullets
    "--ask-bg": "#25303a",       // discussion slides
    "--deck-font": "Georgia, serif"
  }
}
```

Missing tokens fall back to the Paper defaults. Both university themes are
built from published brand swatches and every text/background pair clears
WCAG AA.

## If the network is down

Open the built file from `build/`. No server, no network, everything embedded.
Build the night before — it costs a second and it's the difference between a
presentation and an apology.

## Developing

Use `uv` plus the cross-platform task script:

```bash
git clone https://github.com/techmuch/glissade && cd glissade
uv run python scripts/dev.py install
uv run python scripts/dev.py run
```

That installs Python 3.12 if needed, creates `.venv`, and installs the editable
project with the `dev` and `images` extras. Override the Python version if you
need to:

```bash
uv run python scripts/dev.py install --python 3.11
```

Common tasks:

```bash
uv run python scripts/dev.py install      # bootstrap .venv
uv run python scripts/dev.py test         # run the full test suite
uv run python scripts/dev.py test -- tests/test_check.py -q
uv run python scripts/dev.py run          # defaults to: glissade demo
uv run python scripts/dev.py run -- start
uv run python scripts/dev.py build        # build dist/ packages
```

If you prefer the raw `uv` commands:

```bash
uv python install 3.12
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -e ".[dev,images]"   # Windows: .venv\Scripts\python.exe
uv run --python .venv/bin/python pytest -q                     # Windows: .venv\Scripts\python.exe
```

`src/glissade/` is the package; `templates/` holds the deck and remote HTML;
`data/` holds the themes, JSON schema, `init` scaffold and demo decks — all
shipped inside the wheel so the tool works from any directory.

```bash
uv build                   # sdist + universal wheel into dist/
```
