# Building slides in this project

This directory is a **Glissade** project. Decks are JSON files in `decks/`.
This file is the working reference for building them.

Run `glissade check` after every edit. It catches missing media, unknown
layouts, empty slides and YouTube links in the wrong form, and it is the
fastest way to know a deck is sound. Treat a non-zero exit as work unfinished.

```bash
glissade check          # validate every deck (errors, warnings, design tips)
glissade shoot          # screenshot every slide to build/shots/ and report layout problems
glissade start          # present, with a phone remote and live deck reloads
glissade build          # write standalone HTML to build/
```

**Look at what you made.** `check` reads the JSON; `glissade shoot` renders
it and saves a PNG per slide, then reports overflow, headings that jump
between slides, sparse slides, text squeezed into part of a column, and text
too small to read in a room. Open the PNGs. A deck that passes `check` can
still look wrong. (`shoot` needs Playwright: `pip install playwright` and
`playwright install chromium`.)

---

## The shape of a deck

```jsonc
{
  "$schema": "./glissade.schema.json",
  "title": "Shown in the picker and the browser tab",
  "subtitle": "Optional",
  "theme": "parchment",
  "order": 1,
  "slides": [ /* … */ ]
}
```

`theme` is the theme the deck opens in — an id from `glissade themes`. The
presenter can still switch with **T** or from the remote. Pick one that suits
the material rather than leaving the default.

`glissade.schema.json` sits beside this file. Keep the `$schema` line — it
gives editors autocomplete and inline validation.

Optionally declare the release the deck needs:

```jsonc
"glissade": ">=0.6"
```

Keep the `"format": 1` line. It records the deck format, so a later release
can migrate the file rather than guess at its age.

**Only use fields listed in this document.** Anything else is reported by
`check` and renders nothing — inventing a field does not extend the format.

`glissade check --fix` will correct layout typos, YouTube watch links and a
missing format stamp for you. It will not invent content or rename fields.

---

## The shape of a slide

Pick a `layout`, fill the fields it uses, skip the rest. Nothing is required.

```jsonc
{
  "title": "Short label for the jump list — not shown on the slide",
  "layout": "media-right",
  "tag": "Part two",
  "cls": "ask",
  "eyebrow": "Small line above the heading",
  "heading": "The heading",
  "subheading": "A supporting line",
  "body": "<p>HTML is allowed in every text field.</p>",
  "bullets": ["A point", {"text": "A title", "sub": "and its explanation"}],
  "quote": "A pull quote", "cite": "Attribution",
  "callout": "<b>This week:</b> the one-line takeaway — always drawn last",
  "source": "Where this came from — a small line at the foot of the slide",
  "image": {"src": "media/chart.png", "alt": "What it shows", "fit": "cover",
            "focus": "center top", "caption": "…"},
  "media": {"file": "media/activity.html"},
  "notes": "Speaker notes. HTML allowed."
}
```

`callout` is a filled box for the takeaway, an invitation or a discussion
question. It always renders after everything else on the slide, whatever
order you write the fields in. `source` cites a quote, figure or chapter.

`focus` anchors a cropped (`cover`) image: keywords or percentages, e.g.
`"right center"`, `"70% 30%"`. Use it when a face would otherwise be cut off.

### Layouts

| Layout | Regions it renders |
| --- | --- |
| `title` | eyebrow, heading, subheading, byline |
| `title-content` | eyebrow, heading, subheading, body, bullets |
| `section` | eyebrow, heading, subheading — a divider, with a rule |
| `title-only` | heading alone |
| `two-content` | heading, then `left` and `right` |
| `comparison` | as two-content, but each side takes a `subheading` |
| `content-caption` | wide media beside a narrow `caption` column |
| `picture-caption` | centred image, `body` used as the caption |
| `media-right` / `media-left` | text one side, image or embed the other |
| `media-caption` | centred media at moderate size |
| `media-full` | media fills the slide; eyebrow, heading and body overlay it. `scrim`: `bottom` (default), `left`, `none` |
| `grid` | two to four `images` |
| `quad-chart` | heading plus four `quads`, each with its own subheading and text or media |
| `cards` | heading, then two to four `cards` side by side; `"numbered": true` numbers them |
| `quote` | heading, a large `quote` + `cite`, beside a panel (`subheading`, `body`, `bullets`) or an `image` |
| `blank` | raw `html`, used verbatim |

A card is `{"title": "…", "body": "…", "source": "…", "image": {…}}` — every
part optional, but give it at least a title or body.

`callout` renders on `title-content`, `two-content`, `comparison`,
`content-caption`, `media-left`/`media-right`, `quad-chart`, `cards` and
`quote`. `source` renders on every layout.

`cls` is independent of layout and combines freely: `"ask"` (dark — for
questions and discussion), `"story"` (warmer), `"center"`.

---

## Rules that matter

**Every slide needs `notes`.** The notes are the point of the tool: they go to
the presenter's phone so the slide itself can stay quiet. A slide with no notes
is an unfinished slide, and `check` will say so.

**`title` is a navigation label, not a heading.** It appears only in the
remote's jump list. Keep it under about 40 characters and make it scannable —
`"Q: What's hardest about this?"` beats `"Discussion slide 3"`.

**Put one idea on a slide.** If the body needs more than about 40 words, split
it or move the detail into `notes`.

**Use `section` dividers.** Audiences navigate a long deck by them.

**Media paths are relative to the deck file.** `"media/chart.png"` means
`decks/media/chart.png` when the deck is `decks/talk.json`.

**Don't put `image` or `media` on a text-only layout** (`title`,
`title-only`, `section`, `title-content`, `cards`). There is no region to
draw it in and it will silently not appear. `check` warns about this.

**Every image needs `alt`.** Say what it shows for someone who can't see it
("Two missionaries looking at a phone beside an open Bible"), not what it is
("photo"). Use `"alt": ""` only for pure decoration. `check` warns when it's
missing.

---

## Designing slides that read

The layouts handle spacing, alignment and type. Your job is to choose the
right one for each idea. `check` prints **tips** for these; they are
judgement calls, not errors, but follow them unless you have a reason.

- **Three or four parallel ideas are `cards`, not bullets.** If every bullet
  has a title and a second line, it wants to be cards. Use
  `"numbered": true` for steps or keys, and put the citation in each
  card's `source`.
- **A quotation is a `quote` slide**, with `cite`. Put what to do with it —
  the scripture it pairs with, the discussion question — in the side panel or
  a `callout`.
- **End a teaching sequence with a `callout`**: the invitation, the takeaway,
  the question to discuss. One or two sentences.
- **Cite with `source`**, not in the body. It keeps the slide clean and the
  reference findable.
- **Open with `media-full`** when you have a strong image. Use
  `"scrim": "left"` and an image `focus` on the right when the subject is on
  the right, so the text never covers a face.
- **Keep headings under ~70 characters, body under ~40 words, bullets to
  six, and a whole slide under ~90 words.** Move the rest into `notes`.
- **Use `cls: "ask"` for discussion slides.** The remote warns the presenter
  that one is coming.
- **Then run `glissade shoot` and look at every PNG.**

**`html` only renders on the `blank` layout.** On any other layout it is
ignored. Reach for `blank` last — laid-out slides stay consistent, freeform
ones drift.

---

## Images and embeds

Images are **embedded** into the built HTML, not linked. Point `src` at a file
beside the deck; the build inlines it, downscaling anything over 2560px. The
deck becomes one file with no folder to forget.

Embeds come in three kinds:

| Field | Behaviour | Needs network |
| --- | --- | --- |
| `"file": "media/game.html"` | Local HTML inlined as the iframe's `srcdoc` | No |
| `"srcdoc": "<html>…"` | Inline markup | No |
| `"src": "https://…"` | External page | **Yes** |

Prefer `file` over `src`. A local activity always works; an external embed
depends on the room's Wi-Fi, and if it fails the slide shows a QR-code
fallback instead of the content.

For YouTube use the **`/embed/`** URL form — `https://www.youtube.com/embed/ID`.
A `watch?v=` link will not embed, and `check` treats it as an error.

`aspect` controls shape: omit it (images fit their own proportions, activities
fill the space, external embeds default to `16:9`), or give `"16:9"`, `"4:3"`,
or `"auto"` to fill the region outright.

---

## Worked examples

A discussion stop — dark, one question, nothing else:

```json
{
  "title": "Q: What would you cut?",
  "layout": "title-content",
  "cls": "ask center",
  "eyebrow": "Discussion",
  "heading": "What would you cut from your last deck?",
  "notes": "<b>4–5 min.</b> Take three or four answers without responding to each. The pause is the feature."
}
```

A point with supporting media:

```json
{
  "title": "Q3 revenue by region",
  "layout": "media-right",
  "eyebrow": "Results",
  "heading": "Growth came from one region",
  "body": "<p>Everything else held flat.</p>",
  "image": {"src": "media/q3-revenue.png", "alt": "Bar chart", "fit": "contain"},
  "notes": "Don't read the chart aloud. Say the one sentence and let them look."
}
```

Two things weighed against each other:

```json
{
  "title": "Build vs buy",
  "layout": "comparison",
  "heading": "Two ways forward",
  "left":  {"subheading": "Build", "body": "<p>Slower, ours, no licence.</p>"},
  "right": {"subheading": "Buy",   "body": "<p>Faster, theirs, renews yearly.</p>"},
  "notes": "Ask which risk they'd rather carry before giving the recommendation."
}
```

---

## Before you hand the deck over

1. `glissade check` exits zero, with no warnings you haven't decided to keep.
2. Every slide has `notes`, and every image has `alt`.
3. Every image referenced actually exists.
4. `glissade shoot` reports no layout problems, and you have looked at the
   PNGs.
5. External embeds are deliberate — `build` lists them, and each is a slide
   that fails without Wi-Fi.
6. `glissade build` succeeds.
