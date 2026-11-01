"""Screenshot a deck and measure how it actually laid out.

`check` reads the JSON; it cannot see that a heading wrapped to three lines or
that a column of text overflowed the slide. This renders the built deck in a
headless browser, saves a PNG of every slide, and measures the result, so an
author -- human or agent -- can look at what the room will see.

Playwright is an optional dependency: the presenting tool must stay
compiler-free and small, and only authors need this.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

INSTALL_HINT = (
    "`glissade shoot` needs Playwright and a browser:\n"
    "      uv tool install --with playwright glissade   (or: pip install playwright)\n"
    "      playwright install chromium"
)

# Layouts whose content is meant to sit in the middle of the screen; the
# heading-position and fill measurements don't apply to them.
STATEMENT_LAYOUTS = {"title", "title-only", "section", "media-full", "blank"}

# Thresholds, as fractions of the viewport height.
HEADING_DRIFT = 0.03      # heading top differs from the deck's usual by >3%
SPARSE_FILL = 0.40        # content occupies less than 40% of the usable height
MIN_TEXT = 0.0155         # smaller than ~17px at 1080p is hard to read in a room
NARROW_MEASURE = 0.6      # text using under 60% of its column, over 2+ lines


class ShootUnavailable(RuntimeError):
    pass


@dataclass
class SlideShot:
    n: int
    title: str
    layout: str
    path: Path
    problems: list[str] = field(default_factory=list)
    heading_top: float | None = None


# Runs inside the page for the active slide. Returns raw measurements; the
# judgement happens in Python so the thresholds live in one place.
_MEASURE_JS = """
() => {
  const H = window.innerHeight;
  const s = document.querySelector('.slide.active');
  if(!s) return null;
  const sr = s.getBoundingClientRect();
  const out = {overflow: Math.max(0, s.scrollHeight - s.clientHeight), headingTop: null,
               fill: null, small: [], narrow: [], broken: []};
  // The heading block starts at its eyebrow when there is one: that block's
  // top edge is what should line up from slide to slide.
  const h = s.querySelector('.text-region h1, .text-region h2, .overlay h1, .overlay h2');
  if(h){
    const eb = h.previousElementSibling;
    const start = (eb && eb.classList.contains('eyebrow')) ? eb : h;
    out.headingTop = (start.getBoundingClientRect().top - sr.top) / H;
  }

  // How much of the usable height the content spans.
  const skip = el => el.matches('.num, .tag, .source');
  let top = Infinity, bottom = -Infinity;
  for(const c of s.children){
    if(skip(c)) continue;
    const r = c.getBoundingClientRect();
    if(r.height <= 0) continue;
    // Shrink-wrap to the content actually drawn inside stretchy regions.
    const leaves = c.querySelectorAll(
      'h1,h2,h3,p,li,blockquote,figcaption,img,.callout,.card,.body,iframe');
    const boxes = leaves.length ? Array.from(leaves).map(x => x.getBoundingClientRect()) : [r];
    for(const b of boxes){
      if(b.height <= 0) continue;
      top = Math.min(top, b.top); bottom = Math.max(bottom, b.bottom);
    }
  }
  const cs = getComputedStyle(s);
  const usable = s.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
  if(isFinite(top) && usable > 0) out.fill = (bottom - top) / usable;

  const label = el => (el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 48);
  const texts = 'p, li, small, cite, h1, h2, h3, .body, .callout, .card-src, figcaption';
  // Only judge elements that hold text directly: a card or a figcaption is
  // sized by its children, and its own (inherited) size is never drawn.
  const ownText = el => Array.from(el.childNodes).some(
    n => n.nodeType === 3 && n.nodeValue.trim());
  for(const el of s.querySelectorAll(texts)){
    if(el.closest('.num, .tag')) continue;
    if(!ownText(el)) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if(fs / H < %(min_text)s) out.small.push([label(el), fs]);
  }
  // Text squeezed into part of its column.
  for(const el of s.querySelectorAll('.cols p, .cols ul, .cols .body, .cols blockquote')){
    const col = el.closest('.region, .side-panel, .figure') || el.parentElement;
    const lh = parseFloat(getComputedStyle(el).lineHeight) || 1;
    const r = el.getBoundingClientRect(), cr = col.getBoundingClientRect();
    if(cr.width > 0 && r.height / lh > 2.2 && r.width / cr.width < %(narrow)s)
      out.narrow.push([label(el), Math.round(100 * r.width / cr.width)]);
  }
  // A word wider than its box breaks mid-word or spills out.
  for(const el of s.querySelectorAll('h1, h2, h3, .card h3, li, p')){
    if(el.scrollWidth > el.clientWidth + 2) out.broken.push(label(el));
  }
  return out;
}
"""


def _parse_size(size: str) -> tuple[int, int]:
    try:
        w, h = (int(x) for x in size.lower().split("x"))
        if w < 320 or h < 240:
            raise ValueError
        return w, h
    except ValueError as exc:
        raise ValueError(f"--size must look like 1920x1080, got {size!r}") from exc


def parse_selection(spec: str | None, total: int) -> list[int]:
    """'1,3,5-7' to [1, 3, 5, 6, 7], clipped to the deck."""
    if not spec:
        return list(range(1, total + 1))
    chosen: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            chosen.update(range(int(a), int(b) + 1))
        else:
            chosen.add(int(part))
    return sorted(n for n in chosen if 1 <= n <= total)


def shoot_deck(
    deck: dict[str, Any],
    out_dir: Path,
    themes: list[dict[str, Any]],
    size: str = "1920x1080",
    slides: str | None = None,
    theme: str | None = None,
) -> list[SlideShot]:
    """Render, screenshot and measure the chosen slides of one deck."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ShootUnavailable(INSTALL_HINT) from exc

    from .build import build_deck

    width, height = _parse_size(size)
    selection = parse_selection(slides, len(deck["slides"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("slide-*.png"):
        old.unlink()

    with tempfile.TemporaryDirectory(prefix="glissade-shoot-") as tmp:
        built = build_deck(deck, Path(tmp), themes).path
        shots: list[SlideShot] = []
        try:
            pw = sync_playwright().start()
        except Exception as exc:  # pragma: no cover - environment specific
            raise ShootUnavailable(INSTALL_HINT) from exc
        try:
            try:
                browser = pw.chromium.launch()
            except Exception as exc:
                raise ShootUnavailable(
                    f"Couldn't start Chromium ({exc.__class__.__name__}).\n      "
                    "Run `playwright install chromium`."
                ) from exc
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(built.as_uri(), wait_until="load")
            page.evaluate("() => { try{ localStorage.clear() }catch(e){} }")
            page.reload(wait_until="load")
            # The help pill is for the presenter; never in a screenshot.
            page.add_style_tag(content="#help{display:none !important}")
            if theme:
                page.evaluate("id => applyTheme(id, false)", theme)
            page.evaluate("() => document.fonts && document.fonts.ready")
            for n in selection:
                page.evaluate("k => render(k)", n - 1)
                page.wait_for_function(
                    "() => Array.from(document.querySelectorAll('.slide.active img'))"
                    ".every(i => i.complete)"
                )
                page.wait_for_timeout(350)   # the slide's fade-in
                path = out_dir / f"slide-{n:02d}.png"
                page.screenshot(path=str(path))
                s = deck["slides"][n - 1]
                shot = SlideShot(
                    n=n,
                    title=str(s.get("title") or f"Slide {n}"),
                    layout=str(s.get("layout") or "blank"),
                    path=path,
                )
                _judge(shot, page.evaluate(_MEASURE_JS % {
                    "min_text": MIN_TEXT, "narrow": NARROW_MEASURE,
                }), s, height)
                shots.append(shot)
            browser.close()
        finally:
            pw.stop()

    _judge_headings(shots)
    return shots


def _judge(shot: SlideShot, m: dict | None, slide: dict, height: int) -> None:
    if not m:
        shot.problems.append("slide did not render")
        return
    statement = shot.layout in STATEMENT_LAYOUTS or "center" in str(slide.get("cls", ""))
    if m["overflow"] > 2:
        shot.problems.append(
            f"content overflows the slide by {m['overflow']}px — it will scroll. "
            "Cut text or split the slide."
        )
    if not statement:
        shot.heading_top = m["headingTop"]
        if m["fill"] is not None and m["fill"] < SPARSE_FILL:
            shot.problems.append(
                f"content fills {round(100 * m['fill'])}% of the slide height. "
                "Consider cards, a callout, an image, or merging with a neighbour."
            )
    seen = set()
    for text, px in m["small"]:
        if text in seen:
            continue
        seen.add(text)
        shot.problems.append(
            f"text at {px:.0f}px ({100 * px / height:.1f}vh) is small for a room: “{text}”"
        )
        if len(seen) >= 3:
            break
    for text, pct in m["narrow"][:2]:
        shot.problems.append(f"text uses only {pct}% of its column width: “{text}”")
    for text in m["broken"][:2]:
        shot.problems.append(f"a word is wider than its box and breaks or spills: “{text}”")


def _judge_headings(shots: list[SlideShot]) -> None:
    """Flag headings that sit somewhere other than where most slides put them."""
    tops = sorted(s.heading_top for s in shots if s.heading_top is not None)
    if len(tops) < 3:
        return
    usual = tops[len(tops) // 2]
    for s in shots:
        if s.heading_top is not None and abs(s.heading_top - usual) > HEADING_DRIFT:
            s.problems.append(
                f"heading sits at {round(100 * s.heading_top)}% of the height; "
                f"most slides put it at {round(100 * usual)}%. It will appear to jump."
            )
