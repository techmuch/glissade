# Building slides in this project

This directory is a **Glissade** project. Decks are JSON files in `decks/`.
This file is the working reference for building them.

Run `glissade check` after every edit. It catches missing media, unknown
layouts, empty slides and YouTube links in the wrong form, and it is the
fastest way to know a deck is sound. Treat a non-zero exit as work unfinished.

```bash
glissade check          # validate every deck
glissade start          # present, with a phone remote
glissade build          # write standalone HTML to build/
```

---

## The shape of a deck

```jsonc
{
  "$schema": "./glissade.schema.json",
  "title": "Shown in the picker and the browser tab",
  "subtitle": "Optional",
  "order": 1,
  "slides": [ /* … */ ]
}
```

`glissade.schema.json` sits beside this file. Keep the `$schema` line — it
gives editors autocomplete and inline validation.

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
  "bullets": ["A point", {"text": "With a second line", "sub": "smaller"}],
  "quote": "A pull quote", "cite": "Attribution",
  "image": {"src": "media/chart.png", "alt": "…", "fit": "cover", "caption": "…"},
  "media": {"file": "media/activity.html"},
  "notes": "Speaker notes. HTML allowed."
}
```

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
| `media-full` | media fills the slide; heading and body overlay it |
| `grid` | two to four `images` |
| `blank` | raw `html`, used verbatim |

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
`title-only`, `section`, `title-content`). There is no region to draw it in
and it will silently not appear. `check` warns about this.

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

1. `glissade check` exits zero.
2. Every slide has `notes`.
3. Every image referenced actually exists.
4. External embeds are deliberate — `build` lists them, and each is a slide
   that fails without Wi-Fi.
5. `glissade build` succeeds.
