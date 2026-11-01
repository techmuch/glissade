# 2. A slide design system: anchored layout, design blocks, paired type, and seeing the result

Date: 2026-11-01

## Status

Accepted

## Context

A lesson deck written in Glissade was compared with the same lesson built
by hand on a fixed 1920×1080 canvas. The hand-built slides read far better,
and the gap came from four places:

1. **Layout.** Text stacks were vertically centred, so the heading sat at a
   different height on every slide. Character-based measures (`max-width:44ch`)
   applied inside half-width columns, squeezing text into part of a column.
   Fields rendered in a fixed order, so a closing invitation landed above the
   list it concluded.
2. **Vocabulary.** Every slide was text plus hollow-circle bullets. The
   hand-built deck used cards, numbered steps, a quote panel, a filled
   callout and a source footer — none of which a deck could express.
3. **Type and colour.** Each theme had one typeface for everything, a deck
   could not say which theme it was designed for, and font names in themes
   were never loaded. The default theme's discussion-slide accent was 4.16:1,
   below WCAG AA.
4. **Feedback.** `check` reads JSON. Neither a person nor an agent could see
   how a deck laid out without opening a browser by hand.

## Decision

1. **Anchored layout.** Laid-out slides start at a fixed top margin;
   statement layouts (`title`, `title-only`, `section`) and `center` stay
   centred. Inside columns the column is the measure. A `callout` always
   renders last.
2. **Design blocks as data, not HTML.** New layouts `cards` (two to four,
   optionally `numbered`) and `quote` (quote + cite beside a panel or image);
   new fields `callout`, `source`, `scrim` (media-full), `image.focus`. Each
   renders semantic markup: an ordered list for numbered cards, a `figure`
   with `figcaption` for quotes, `role="note"` for callouts, a `footer` for
   sources. Freeform `blank` stays the escape hatch, not the answer.
3. **Paired type and checked colour.** Themes gain `--display-font` and
   `--body-font` (falling back to `--deck-font`), a single five-step type
   scale, a `palette` shorthand (dark, light, accents → every token, each
   text colour pushed to AA), and `fonts` (local files embedded as
   `@font-face`). A deck may name its `theme`. `check` reports any
   text/background pair under 4.5:1; every built-in theme passes.
4. **See the result.** `glissade shoot` builds the deck, renders each slide in
   headless Chromium, saves PNGs, and measures overflow, heading drift,
   sparse fill, squeezed measures, broken words and small text. Playwright is
   an optional extra (`glissade[shoot]`) so presenting stays dependency-light.
   `check` adds a `tip` level for design judgement calls (word counts, bullets
   that want to be cards, quotes without `cite`) that never fails a check.
5. **Accessibility is part of the design, not a pass at the end.** Slides are
   labelled groups with a live-region announcement on change; dialogs (deck
   switcher, remote drawer) manage focus; remote controls expose
   `aria-pressed` / `aria-expanded` / `aria-current`; reduced motion is
   honoured; pinch-zoom is allowed; images without `alt` are warned about.
   Changes were verified with axe-core (zero violations on the lesson deck and
   remote).

## Consequences

- Existing decks render with the new spacing and type without edits; themes
  that set only `--deck-font` keep one face for both roles.
- The schema and checker gained fields; decks using them should declare
  `"glissade": ">=0.15"`. Older releases warn rather than silently dropping
  content.
- `:has()` is used for column sizing; current Chromium, Safari and Firefox
  support it. Older browsers fall back to stretched columns, which is the
  previous behaviour.
- `shoot` thresholds are heuristics and live in one place (`shoot.py`).
