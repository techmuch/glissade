# Glissade

Presentation decks written as JSON, driven from your phone, and built into a
single HTML file that works when the Wi-Fi doesn't.

```bash
uv tool install glissade     # or: pipx install glissade

mkdir my-talk && cd my-talk
glissade init                # scaffold a deck and an AI-agent guide
glissade start               # present — prints a QR code for the remote
```

No project yet? `glissade demo` runs the decks that ship with the tool from
anywhere, and they document the whole system.

## Installing

| | |
| --- | --- |
| **uv** (recommended) | `uv tool install glissade` — installs Python too if you don't have it |
| **pipx** | `pipx install glissade` |
| **pip** | `pip install glissade` |
| **Try without installing** | `uvx glissade demo` |

One universal wheel covers Windows, macOS and Linux — every dependency is pure
Python, so installation never needs a compiler. Python 3.10 or newer.

Add `glissade[images]` to pull in Pillow, which downscales oversized images
before embedding them. Without it images embed at full size; nothing breaks.

## Commands

| Command | Does |
| --- | --- |
| `glissade init [dir]` | Scaffold a project: a starter deck, `AGENTS.md`, and the JSON schema |
| `glissade start` | Present, with a phone remote on the same Wi-Fi |
| `glissade build [deck]` | Write standalone HTML to `build/` |
| `glissade check [deck]` | Validate decks — run this after editing |
| `glissade decks` / `themes` | List what's available |
| `glissade demo` | Present the built-in tour and layout gallery |

Every command takes `-C PATH` to run as if started elsewhere. Commands find
your project by walking up from the working directory, the way git does, so
they work from any subdirectory.

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

On Windows the first run may raise a firewall prompt: allow private networks
so your phone can reach the remote. `--host 127.0.0.1` avoids it if you only
want the laptop.

### The remote

The main view holds only what you read while presenting — the current slide's
speaker notes and a preview of the next one. Everything else sits behind a
header button: **Deck**, **Slides** (jump list), and a gear for text size and
theme. **Blank** blacks out the projector.

### Keys on the projecting machine

| Key | Does |
| --- | --- |
| <kbd>←</kbd> <kbd>→</kbd> | navigate |
| <kbd>N</kbd> | speaker notes on screen |
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
`media-left`, `media-full`, `media-caption`, `grid`, `blank`.

`cls` adds modifiers independent of layout: `"ask"` (dark, for questions),
`"story"`, `"center"`.

Run `glissade demo --deck gallery` to see all fourteen.

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

```bash
git clone https://github.com/techmuch/glissade && cd glissade
uv venv && uv pip install -e ".[images]"
glissade demo
```

`src/glissade/` is the package; `templates/` holds the deck and remote HTML;
`data/` holds the themes, JSON schema, `init` scaffold and demo decks — all
shipped inside the wheel so the tool works from any directory.

```bash
python -m build            # sdist + universal wheel into dist/
```
