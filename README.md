# Slidecast

Presentation decks written as JSON, driven from your phone, and built into a
single HTML file that works when the Wi-Fi doesn't.

```bash
pixi run start      # present — prints a QR code for the remote
pixi run build      # write every deck to build/ as a standalone file
```

Two decks ship, and both are documentation:

| Deck | What it is |
| --- | --- |
| **Slidecast — A Tour** | `pixi run tour` — what it does and how to drive it |
| **Layout Gallery** | `pixi run gallery` — all fourteen layouts, one per slide |

Switch between them from the remote, or with `--deck <id>`.

## Presenting

`pixi run start` prints two addresses and a QR code:

| Address | Open it on |
| --- | --- |
| `http://<your-ip>:8000/` | the machine driving the projector — press **F** for fullscreen |
| `http://<your-ip>:8000/control` | your phone (scan the QR) |

Both devices must be on the same Wi-Fi. The server holds the slide position, so
whoever advances — phone or laptop — everyone follows, and a device that
reconnects lands on the right slide.

`pixi run local` binds to localhost only, if you'd rather run the remote in a
second window on the same machine.

### The remote

The main view holds only what you read while presenting:

- **Now showing** — full speaker notes for the current slide
- **Up next** — a live preview of the slide you're about to advance to
- **Back / Next** — thumb-sized buttons; swipes work too

Everything else is a panel behind a header button:

| Button | Opens |
| --- | --- |
| **Blank** | (toggles directly — blacks out the projector) |
| **Deck** | Deck picker |
| **Slides** | The full jump list, with discussion stops flagged |
| **⚙** | Text size and theme |

Picking a slide or a deck closes the panel; changing size or theme leaves it
open so you can judge the result against the wall.

It holds a screen wake lock so your phone shouldn't sleep. Bluetooth clickers
work — most send arrow keys.

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

## Writing a deck

A deck is one JSON file in `decks/`. Anything you drop there is discovered
automatically and appears in the remote's picker.

```jsonc
{
  "title": "My Talk",              // shown in the picker and the browser tab
  "subtitle": "Optional",
  "order": 3,                      // sort position in the picker
  "slides": [ /* … */ ]
}
```

A bare `[ … ]` array of slides works too — the title is then taken from the
filename.

### A slide

Pick a `layout` and fill the fields it uses. Nothing is required.

```jsonc
{
  "n": 9,
  "layout": "media-right",
  "tag": "Part two",             // small corner label
  "cls": "ask",                  // "ask" (dark), "story", "center" — combinable
  "eyebrow": "Above the heading",
  "heading": "The heading",
  "subheading": "…",
  "body": "<p>HTML is fine here.</p>",
  "bullets": ["A point", {"text": "With a sub-line", "sub": "smaller text"}],
  "quote": "…", "cite": "…",
  "image":  {"src": "media/images/x.jpg", "alt": "…", "fit": "cover", "caption": "…"},
  "media":  {"src": "https://www.youtube.com/embed/…", "aspect": "16:9"},
  "images": [ {"src": "…", "caption": "…"} ],   // for "grid"
  "left":   { … }, "right": { … },              // for two-content / comparison
  "notes": "Speaker notes — HTML, shown on your phone"
}
```

### Layouts

PowerPoint equivalents: `title`, `title-content`, `section`, `title-only`,
`two-content`, `comparison`, `content-caption`, `picture-caption`, `blank`.

Media layouts: `media-right`, `media-left`, `media-full`, `media-caption`,
`grid`.

`blank` uses the slide's raw `html` verbatim — the escape hatch when no layout
fits. Run `pixi run gallery` to see all fourteen.

## Media

### Images are embedded, not linked

Point `src` at a file beside your deck. At build time it's read, downscaled if
larger than 2560px, and written into the HTML as a data URI — so the deck stays
a single file with no sibling folders to forget. Paths resolve relative to the
deck's own directory.

### Embeds

| Field | What it does | Needs internet |
| --- | --- | --- |
| `"file": "media/activities/x.html"` | Local HTML inlined as the iframe's `srcdoc` | No |
| `"srcdoc": "<html>…"` | Markup written straight into the JSON | No |
| `"src": "https://…"` | External page — YouTube, an online activity | **Yes** |

Local activities are sandboxed to `allow-scripts`: they run their own code but
can't reach the deck. For YouTube use the **`/embed/`** URL form.

### Sizing

Media is measured against the space actually available and sized to fill it —
whichever of width or height binds first decides, and the other follows from
the ratio. It refits when the window resizes, the text size changes, or the
notes panel opens.

`aspect` controls the shape:

| Value | Behaviour |
| --- | --- |
| omitted | Images fit their own proportions; **activities fill all available space**; external embeds default to `16:9` |
| `"16:9"`, `"4:3"`, `"1:1"` | Hold that ratio, as large as fits |
| `"auto"` | Fill the region entirely, ignoring proportions |

`media-full` always fills, whatever the slide asks for.

Two behaviours worth knowing:

- **Embeds mount only while their slide is on screen.** Every slide lives in
  the DOM at once, so a mounted iframe would keep a video playing — and
  audible — after you advanced. Leaving a slide destroys the iframe, which is
  what actually stops playback. Nothing loads until you arrive.
- **External embeds fall back to a QR code.** If one can't load within six
  seconds the slide shows the URL and a scannable code rather than a blank
  frame. <kbd>R</kbd> retries.

While you're clicking inside an activity, arrow keys go to the activity — use
the phone remote to advance.

`pixi run build` names every slide that depends on the network:

```
  2 embed(s) need live internet:
    Slidecast — A Tour slide 17: https://www.youtube.com/embed/…
```

## Themes

| Theme | Look |
| --- | --- |
| **Paper** | Warm paper and muted gold. The default — easy on a dim projector. |
| **Georgia Tech** | Official GT palette: Tech Gold, Navy Blue, Diploma ivory. |
| **Texas A&M** | Official A&M palette: Aggie Maroon and white, with the Aggie brand typefaces. |

Press <kbd>T</kbd> or tap a swatch on the remote. The server holds the value so
the remote and the wall agree, and it's saved between runs.

Both university themes are built from published brand swatches, and every
text/background pair in all three themes clears WCAG AA.

**Georgia Tech** follows GT's own accessibility guidance: Tech Gold (`#B3A369`)
is used only for rules and bullets, never text, since GT flags it as
inaccessible on light backgrounds. Text gold is their Tech Dark Gold darkened
to `#7f6f34` to clear AA on Diploma ivory (4.58:1 rather than 4.25:1).

**Texas A&M** needed no such adjustment — every swatch is used unmodified, and
the tightest pair still measures 8.93:1. Discussion slides flood Aggie Maroon
(`#500000`). Type follows the Aggie brand fonts: Oswald for the uppercase
micro-labels, which is its stated job, and Work Sans for headings and body.
A&M name Georgia as their own digital substitute for Crimson Text, and it's a
system font, so it's the guaranteed fallback when the brand fonts aren't
installed.

### Adding one

Add an entry to `themes.json` — no code changes. The deck takes every colour
and typeface from these tokens:

```jsonc
{
  "id": "midnight",
  "name": "Midnight",
  "vars": {
    "--paper": "#12151a",        // slide background
    "--ink": "#f2f4f7",          // headings
    "--ink-soft": "#aab4c0",     // body text
    "--accent": "#d8b169",       // eyebrows, citations, emphasis
    "--accent-light": "#8a6f3c", // quote bars, bullets
    "--rule": "#252b33",         // hairlines
    "--surround": "#05070a",     // letterbox around the slide
    "--story-bg": "#171b21",     // "story" slides
    "--ask-bg": "#d8b169",       // "ask" slides
    "--ask-ink": "#1a1408",
    "--ask-ink-soft": "#3d3117",
    "--ask-heading": "#0d0a04",
    "--ask-accent": "#5a4718",
    "--overlay-bg": "rgba(5,7,10,.95)",   // notes overlay / toast
    "--overlay-ink": "#e8ecf1",
    "--chrome-ink": "#5c6672",            // small corner hints
    "--blank-bg": "#000000",              // the B blackout
    "--deck-font": "Georgia, serif",
    "--ui-font": "Helvetica, Arial, sans-serif",
    "--heading-weight": "400",
    "--heading-tracking": "-0.01em"
  }
}
```

Missing tokens fall back to the Paper defaults, and an unknown or deleted theme
id falls back rather than leaving the deck unstyled. Only fonts already on the
machine are used — nothing is downloaded.

## Files

| Path | What it is |
| --- | --- |
| `decks/*.json` | Your decks — **the source of truth** |
| `decks/media/` | Images and activities the decks reference |
| `themes.json` | Colour and typeface definitions |
| `build/` | Generated standalone decks (gitignored) |
| `slidecast/` | The presentation server |

## If the network is down

Open the built file from `build/` — no server, no network, everything embedded.
Arrow keys navigate, **N** shows notes, **+**/**−** resize, **T** changes
theme, **F** fullscreen. The one thing that won't work is an external embed,
which shows its QR fallback instead.

Build the night before. It costs a second and it's the difference between a
presentation and an apology.
