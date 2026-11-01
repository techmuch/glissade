# Glissade

[![Website](https://img.shields.io/badge/Website-techmuch.github.io%2Fglissade-amber?style=flat-square)](https://techmuch.github.io/glissade/)

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
| `glissade check [deck]` | Validate decks and themes, with design tips — `--fix` applies the obvious corrections |
| `glissade shoot [deck]` | Screenshot every slide to `build/shots/` and report layout problems (needs Playwright) |
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
  warn    slide 4: image has no alt text
  tip     slide 5: every bullet has a title and a second line
            Three or four parallel ideas usually read better as a `cards` layout.
```

Tips are design judgement calls — word counts, a quote without a citation,
bullets that want to be cards — and never fail the check (`--no-tips` hides
them).

The second half of the loop is `glissade shoot`. It renders the deck in a
headless browser, saves a PNG of every slide, and measures the result:

```
  slide 4  Activity  (two-content)
    ! heading sits at 8% of the height; most slides put it at 14%. It will appear to jump.
  slide 6  Armor of God  (media-right)
    ! content overflows the slide by 64px — it will scroll. Cut text or split the slide.
```

It reports overflow, headings that jump between slides, sparse slides, text
squeezed into part of its column, words too wide for their box, and text too
small to read in a room. An agent that can see its slides fixes most of these
on its own. `shoot` needs Playwright, which only authors need:

```bash
uv tool install --with playwright glissade   # or: pip install 'glissade[shoot]'
playwright install chromium
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

`glissade start` also watches your project while it is running. Edit a deck
JSON file, swap an image under `decks/`, or change `themes.json`, and every
connected display and remote refreshes to the newest valid version
automatically. If an edit leaves the deck invalid JSON, Glissade keeps showing
the last good version and logs the reload error instead.

`glissade start --open` opens the deck in your browser once the server is
actually accepting connections — put `open = true` in `glissade.toml` to make
that a project's default. Use `--no-watch` if you want a fixed presentation
that ignores on-disk changes.

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
| <kbd>D</kbd> | switch deck overlay |
| <kbd>+</kbd> <kbd>−</kbd> <kbd>0</kbd> | text size (70–160%) |
| <kbd>T</kbd> | cycle theme |
| <kbd>R</kbd> | reload a failed embed |
| <kbd>F</kbd> | fullscreen |
| <kbd>?</kbd> | show these keys (they appear briefly on load, then get out of the way) |

### Accessibility

The projected deck and the remote are built to work with a keyboard and a
screen reader, and are checked with axe-core:

- Each slide is a labelled group ("slide, 3 of 6: heading"); slide changes are
  announced through a live region. Pull quotes are figures with captions,
  numbered cards are ordered lists, callouts are notes.
- The deck switcher and the remote's drawer are proper dialogs: focus moves in
  when they open, Tab stays inside, Escape closes, and focus returns to where
  it was.
- Remote buttons expose their state (`aria-pressed`, `aria-expanded`,
  `aria-current`); the connection dot has a text label; pinch-zoom works.
- Motion is off under `prefers-reduced-motion`, and every interactive element
  has a visible focus ring.
- Every built-in theme clears WCAG AA for each text/background pair it draws,
  `glissade check` reports any project theme that doesn't, and it warns about
  images without `alt` text.

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
`media-left`, `media-full`, `media-caption`, `grid`, `quad-chart`, `cards`,
`quote`, `blank`.

`cls` adds modifiers independent of layout: `"ask"` (dark, for questions),
`"story"`, `"center"`.

### Design blocks

Laid-out slides anchor their heading to the same place on every slide, size
text to the column it sits in, and share one type scale. On top of that:

| Block | What it is |
| --- | --- |
| `cards` layout | Two to four parallel ideas side by side — `{title, body, source, image}` each; `"numbered": true` for steps |
| `quote` layout | A large `quote` and `cite`, beside a panel (`subheading`, `body`, `bullets`) or an `image` |
| `callout` | A filled box for the takeaway or the question — always the last thing on the slide |
| `source` | A small citation line pinned to the foot of any slide |
| `scrim` | On `media-full`: `bottom`, `left` or `none` — where the image darkens behind the text |
| `image.focus` | Where a cropped image anchors: `"right center"`, `"70% 30%"` |

```jsonc
{
  "layout": "cards", "numbered": true,
  "eyebrow": "How to search", "heading": "Three keys to meaningful study",
  "cards": [
    {"title": "Seek the Spirit", "body": "Pray first.", "source": "Moroni 10:5"},
    {"title": "Bring questions", "body": "Write them down first."},
    {"title": "Live what you learn", "body": "Act on one thing.", "source": "John 7:17"}
  ],
  "callout": "<b>This week:</b> pick one key and try it.",
  "source": "Preach My Gospel, chapter 2"
}
```

Run `glissade demo --deck gallery` to see all seventeen.

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

**Paper** (default), **Parchment**, **Georgia Tech**, and **Texas A&M** ship
with the tool. Press <kbd>T</kbd> or pick one on the remote. A deck can name
the theme it opens in with a top-level `"theme": "parchment"`; the presenter
can still switch.

Each theme pairs two typefaces: a display face for headings and quotes
(`--display-font`) and a body face for reading text (`--body-font`).

Drop a `themes.json` in your project to replace them with your own. The
quickest way is a **palette**: one dark, one light, one or two accents. The
other tokens are derived, and every derived text colour is pushed until it
clears WCAG AA against what it sits on:

```jsonc
{
  "id": "housestyle",
  "name": "House style",
  "palette": {
    "dark": "#2b2118", "light": "#f7f1e6",
    "accent": "#9a4e1f", "accent2": "#e9b27d",
    "display_font": "'EB Garamond', Georgia, serif",
    "body_font": "'Public Sans', -apple-system, sans-serif"
  },
  "fonts": [
    {"family": "EB Garamond", "src": "fonts/EBGaramond.woff2", "weight": "400 700"},
    {"family": "Public Sans", "src": "fonts/PublicSans.woff2", "weight": "400 700"}
  ],
  "vars": { "--heading-weight": "500" }   // anything here overrides the palette
}
```

`fonts` lists font files beside `themes.json`; they are embedded in the page
as `@font-face` rules, so the deck keeps its typefaces with no network. You
can also set every token by hand in `vars` (`--paper`, `--ink`, `--ink-soft`,
`--accent`, `--accent-light`, `--ask-bg`, `--callout-bg`, `--display-font`,
`--body-font`, …); missing ones fall back to the Paper defaults.

`glissade check` reports any text/background pair in your themes that falls
below WCAG AA (4.5:1). Every built-in theme passes.

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
uv run python scripts/dev.py test         # run the default test suite (excludes browser e2e)
uv run python scripts/dev.py test -- tests/test_check.py -q
uv run python scripts/dev.py run          # defaults to: glissade demo
uv run python scripts/dev.py run -- start
uv run python scripts/dev.py build        # build dist/ packages
uv run python scripts/dev.py e2e-install  # install Playwright's browser binaries
uv run python scripts/dev.py e2e          # run browser end-to-end tests
```

If you prefer the raw `uv` commands:

```bash
uv python install 3.12
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -e ".[dev,images]"   # Windows: .venv\Scripts\python.exe
uv run --python .venv/bin/python pytest -q                     # Windows: .venv\Scripts\python.exe
uv run --python .venv/bin/python python -m playwright install chromium
uv run --python .venv/bin/python pytest -m e2e tests/e2e -q
```

`src/glissade/` is the package; `templates/` holds the deck and remote HTML;
`data/` holds the themes, JSON schema, `init` scaffold and demo decks — all
shipped inside the wheel so the tool works from any directory.

Browser behavior is covered by Playwright end-to-end tests in `tests/e2e/`.
They start a real `glissade` server, drive both the projector and remote UIs,
and verify live navigation, live notes, and watch-mode reloads.

```bash
uv build                   # sdist + universal wheel into dist/
```
