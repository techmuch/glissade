# Changelog

Notable changes to Glissade. Decks can declare the release they need with
`"glissade": ">=2026.11.1"`.

Releases are numbered by date: `year.month.day.release`, unpadded, with
`release` counting from 0 within a day (`2026.11.1.0`, then `2026.11.1.1`).
Git tags add a `v` (`v2026.11.1.0`). Releases up to 0.15.0 used `0.x`
numbers and keep them; every calendar release sorts above them.

## 2026.11.1.0 — 2026-11-01

### Added
- **Themes inside a deck.** `"theme"` may now be an object with the same
  `palette`, `vars`, `fonts` and `extends` as a `themes.json` entry, so a deck
  carries its own look in one file. It opens in that theme, appears on the
  remote and with <kbd>T</kbd> as "<name> (this deck)" only while that deck
  is open, and is embedded in builds with its fonts (resolved beside the deck
  file). `check` gives it contrast, font, `extends` and unknown-field checks;
  `glissade themes` lists it as `deck:<deck id>`. The demo Layout Gallery now
  carries its own theme.
- **`extends` for themes.** A theme can start from another by id and change
  only what it sets. In a project's `themes.json` it can extend another entry
  or a built-in theme. Loops and unknown ids are reported by `check`, not fatal.

### Versioning
- Switched to calendar versions (see above). Earlier releases keep their
  numbers. Decks that require `">=0.15"` or any other `0.x` release still work.
- Version comparison now uses every part of the number. Before, it read only
  the first three, so two releases on the same day would have looked
  identical to `glissade upgrade` and to deck requirements. A leading `v`
  (as on git tags) is accepted.

### Security
- **The remote now needs a control key.** `glissade start` generates a random
  key each run and puts it in the printed Slides and Remote links and the QR
  code. Commands (`POST /api/*`) from other machines without it are refused,
  so nobody else on venue Wi-Fi can drive your slides. Viewing stays open, and
  the machine running Glissade never needs the key. Set `key = "..."` in
  `glissade.toml` for a fixed key, or pass `--no-key` to turn it off. The
  remote shows a notice when its key is refused.

### Fixed
- `check --fix` now rewrites YouTube watch links inside quad-chart slides,
  which `check` already reported as errors.
- The build's "needs live internet" report now lists remote images in grid,
  card and two-column slides; it previously missed them.
- `check` warns about missing alt text on remote and `data:` images too.
- Running `check --fix` twice no longer overwrites the first `.bak`, so the
  backup is always the file as it was before Glissade touched it.
- A slide whose text happens to contain a template token such as `__TITLE__`
  renders as written instead of being substituted.
- A non-numeric `order` in a deck or `port` in `glissade.toml` is handled
  instead of crashing.
- The remote's preview escapes plain text (decoded `blank`-slide lines, embed
  URLs) before inserting it into the page.
- Switching themes no longer leaves the previous theme's tokens behind. A
  token the new theme doesn't set now falls back to the default, on the
  projector and in the remote's preview.
- After a deck switch, the remote reloads its theme list as well as its slides.
- `glissade themes --demo` lists the demo project's themes.

### Changed
- `check --fix` plans and applies in a single pass, so what it reports is
  exactly what it changes.
- Every place a slide can hold an image or embed is found by one helper
  (`assets.media_nodes`), shared by inlining, the offline report and `--fix`.
- The deck template is split into `deck.html`, `deck.css` and `deck.js`,
  still inlined into one self-contained page.
- The inlined-file cache keeps one entry per file, so a long watch session
  doesn't accumulate every version of an edited image.
- Deck files are parsed once during discovery instead of twice.
- The package version is defined only in `src/glissade/__init__.py`.
- CI runs on Windows and Python 3.14.

### Tests
- New coverage for live reload and the file watcher, deck switching, saved
  settings and live notes, `upgrade` version parsing and requirements,
  `update`'s handling of edited files, the control key, and template rendering.

## 0.15.0
- Slide design system: anchored layout, `cards` and `quote` layouts, `callout`,
  `source`, `scrim` and `image.focus`; paired display/body fonts, palette
  shorthand and embedded theme fonts; WCAG contrast checks in `check`.
- `glissade shoot`: headless screenshots of every slide with layout problem
  detection (optional `glissade[shoot]` extra).
- Accessibility pass on the deck and remote. See `docs/adr/0002`.

## 0.14.x
- 0.14.4: on-screen deck switcher, opened with <kbd>D</kbd>.
- 0.14.0: browser end-to-end test workflow.

## 0.13.0
- Live reload while presenting: edits to decks, media and `themes.json`
  refresh every connected display; broken JSON keeps the last good version.

## 0.12.0
- `quad-chart` layout.

## 0.10.0 and earlier
- Live notes: an editor on the remote, a projector overlay, and a review drawer.
- Pytest suite and CI (see `docs/adr/0001`).
- `check --fix` and the deck format stamp; `glissade update`; `glissade upgrade`;
  `--open`; clean Ctrl-C shutdown; versioned deck format with unknown-field
  warnings.
- Repackaged as an installable cross-platform CLI and renamed to Glissade.
