/* The deck's behaviour. render_deck() inlines it into deck.html after the
   data constants (SLIDES, THEMES, DECK_THEME, DECKS, DECK_TITLE, LIVE,
   currentDeckId), which it reads as globals. */

document.title = DECK_TITLE;
document.getElementById('stage').setAttribute('aria-label', DECK_TITLE);

/* Keyboard help: visible for a moment on load so it's discoverable, then
   hidden so it never sits on a projected slide. ? or H brings it back. */
const helpEl = document.getElementById('help');
let helpTimer = null;
function showHelp(ms){
  helpEl.classList.add('on');
  clearTimeout(helpTimer);
  helpTimer = setTimeout(() => helpEl.classList.remove('on'), ms || 5000);
}
function toggleHelp(){
  if(helpEl.classList.contains('on')){ clearTimeout(helpTimer); helpEl.classList.remove('on'); }
  else showHelp(8000);
}
showHelp(4000);

const MIN_SCALE = 0.7, MAX_SCALE = 1.6, SCALE_STEP = 0.1;

const stage = document.getElementById('stage');
const notesEl = document.getElementById('notes');
const blankEl = document.getElementById('blank');
const liveNotesEl = document.getElementById('livenotes');
const liveNotesBodyEl = document.getElementById('lnbody');
const liveNotesStateEl = document.getElementById('lnstate');
const liveEl = document.getElementById('live');
const toastEl = document.getElementById('scaletoast');
const deckPickerEl = document.getElementById('deckpicker');
const dpListEl = document.getElementById('dplist');
let i = 0, notesOn = false, blanked = false, scale = 1, liveNotesVisible = false, liveNoteText = '';
let themeId = (THEMES[0] || {}).id || 'paper';
let deckPickerOpen = false, dpFocusedIdx = 0;

/* ==================== layout renderer ====================
   Every layout is built from three region kinds: text, image, and embed.
   A slide with no `layout` is treated as "blank" and its raw `html` is used
   verbatim, so decks written before layouts existed render unchanged. */

function el(tag, cls, html){
  const e = document.createElement(tag);
  if(cls) e.className = cls;
  if(html != null) e.innerHTML = html;
  return e;
}

function aspectRatio(a){
  if(!a) return null;
  if(typeof a === 'number') return a;
  const m = String(a).split(/[:\/x]/);
  if(m.length === 2){
    const w = parseFloat(m[0]), h = parseFloat(m[1]);
    if(w > 0 && h > 0) return w / h;
  }
  const n = parseFloat(a);
  return n > 0 ? n : null;
}

/* Text region: any subset of eyebrow / heading / subhead / body / bullets.
   `body` and bullet text are authored as HTML so quotes and emphasis work. */
function textRegion(o){
  const box = el('div', 'region stack text-region');
  if(o.eyebrow)  box.appendChild(el('div', 'eyebrow', o.eyebrow));
  if(o.heading)  box.appendChild(el(o.headingLevel === 1 ? 'h1' : 'h2', null, o.heading));
  if(o.subheading) box.appendChild(el('div', 'subhead', o.subheading));
  if(o.body)     box.appendChild(el('div', 'body', o.body));
  if(o.bullets && o.bullets.length) box.appendChild(bulletList(o.bullets));
  if(o.quote)    box.appendChild(pullQuote(o.quote, o.cite, o.quoteBig));
  /* The callout always comes last, whatever order the fields were written
     in: it is the takeaway, so it closes the slide. */
  if(o.callout)  box.appendChild(callout(o.callout));
  return box;
}

/* A bullet given as {text, sub} is a title and its explanation; the title
   gets weight so the two read as two levels, not two sizes of the same. */
function bulletList(items){
  const ul = el('ul');
  items.forEach(b => {
    if(b && typeof b === 'object'){
      const li = el('li', b.sub ? 'has-sub' : null);
      li.appendChild(el('span', 'li-t', b.text == null ? '' : String(b.text)));
      if(b.sub) li.appendChild(el('small', null, b.sub));
      ul.appendChild(li);
    } else {
      ul.appendChild(el('li', null, String(b)));
    }
  });
  return ul;
}

/* A quotation and its source belong together, so they are a figure. */
function pullQuote(text, cite, big){
  const f = el('figure', 'pull' + (big ? ' big' : ''));
  f.appendChild(el('blockquote', null, text));
  if(cite){
    const cap = el('figcaption');
    cap.appendChild(el('cite', null, cite));
    f.appendChild(cap);
  }
  return f;
}

function callout(html){
  const c = el('div', 'callout', html);
  c.setAttribute('role', 'note');
  return c;
}

/* Cards: two to four parallel ideas. A numbered set is an ordered list, so
   assistive tech hears "list, 3 items" and the position of each -- the big
   visible numeral is decoration on top of that, and hidden from it. */
function cardList(cards, numbered){
  const items = (Array.isArray(cards) ? cards : []).filter(c => c && typeof c === 'object');
  const n = Math.min(4, Math.max(1, items.length));
  const list = el(numbered ? 'ol' : 'ul', 'cards n' + n);
  list.style.setProperty('--n', n);
  items.forEach((c, k) => {
    const li = el('li', 'card');
    if(c.image && c.image.src){
      const img = el('img', 'card-img');
      img.src = c.image.src;
      img.alt = c.image.alt || '';
      if(c.image.focus) setFocus(img, c.image.focus);
      li.appendChild(img);
    }
    if(numbered){
      const num = el('div', 'card-n', String(k + 1));
      num.setAttribute('aria-hidden', 'true');
      li.appendChild(num);
    }
    if(c.title)  li.appendChild(el('h3', null, c.title));
    if(c.body)   li.appendChild(el('div', 'body', c.body));
    if(c.source) li.appendChild(el('div', 'card-src', c.source));
    list.appendChild(li);
  });
  return list;
}

/* Where to anchor a cropped image: keywords or percentages only. */
function setFocus(img, focus){
  const f = String(focus || '').trim();
  if(/^[a-z0-9%.\s-]{1,40}$/i.test(f)) img.style.objectPosition = f;
}

/* An image or an embed, in a box that can hold an aspect ratio. Embeds are
   NOT created here — only a placeholder is, so nothing loads until the slide
   is actually shown. */
/* "auto" means: take all the space there is, don't hold a ratio. Activities
   want this; a video does not, or it gets letterboxed by the player. */
function defaultAspect(node){
  if(node.kind === 'image') return null;        // images fit via object-fit
  return node.srcdoc != null ? 'auto' : '16:9';
}

function mediaBox(node, opts){
  opts = opts || {};
  /* `force` is for layouts whose shape is not negotiable — full-bleed fills
     the screen whatever the slide asked for. */
  const want = opts.force ? opts.aspect : (node.aspect || opts.aspect || defaultAspect(node));
  const ar = (want === 'auto' || want === 'fill') ? null : aspectRatio(want);
  const box = el('div', 'media-box ' + (ar ? 'ar' : 'fill'));
  if(ar) box.dataset.ar = ar;

  if(node.kind === 'image'){
    const img = el('img');
    img.src = node.src;
    img.alt = node.alt || '';
    if((node.fit || opts.fit) === 'cover') img.className = 'cover';
    if(node.focus) setFocus(img, node.focus);
    if(node.remote) img.addEventListener('error', () => {
      box.appendChild(fallbackPanel(node.src, 'Image could not load'));
      box.querySelector('.embed-fallback').classList.add('on');
    });
    box.appendChild(img);
  } else {
    // Deferred embed: remember the spec, mount on activation.
    box.dataset.embed = '1';
    EMBEDS.set(box, node);
    box.appendChild(fallbackPanel(node.src, node.fallback_label, node.qr));
  }
  return box;
}

function fallbackPanel(url, label, qr){
  const p = el('div', 'embed-fallback');
  p.appendChild(el('div', 'ef-title', label ? 'Can’t reach ' + label : 'This embed needs internet'));
  if(qr){
    const q = el('img');
    q.src = qr; q.alt = 'QR code linking to ' + (url || '');
    p.appendChild(q);
  }
  if(url) p.appendChild(el('div', 'ef-url', url));
  p.appendChild(el('div', 'ef-hint', qr ? 'Scan to open it on a phone' : 'Check the connection and press R to retry'));
  return p;
}

function figure(node, opts){
  const f = el('figure', 'figure region');
  const slot = el('div', 'fitslot');
  slot.appendChild(mediaBox(node, opts));
  f.appendChild(slot);
  if(node.caption) f.appendChild(el('figcaption', 'caption', node.caption));
  return f;
}

/* Normalise "what goes in this region" — a slide may put an image or an embed
   in the same slot, and left/right blocks may carry either. */
function pickMedia(o){
  if(!o) return null;
  if(o.image && typeof o.image === 'object') return Object.assign({kind:'image'}, o.image);
  if(o.media && typeof o.media === 'object') return Object.assign({kind:'embed'}, o.media);
  return null;
}

const EMBEDS = new WeakMap();

/* ---- fit media to the space available ----
   Given the slot's real width and height, take whichever dimension binds and
   derive the other from the ratio. This is what makes an image or an embed as
   large as it can be without overflowing the slide, and it re-runs whenever
   the available area changes -- window resize, text-size change, or the notes
   panel opening. */
function fitBox(box){
  const ar = parseFloat(box.dataset.ar);
  const slot = box.parentElement;
  if(!ar || !slot) return;
  const W = slot.clientWidth, H = slot.clientHeight;
  if(W <= 0 || H <= 0) return;                 // not laid out yet
  let w = W, h = W / ar;
  if(h > H){ h = H; w = H * ar; }
  box.style.width  = Math.floor(w) + 'px';
  box.style.height = Math.floor(h) + 'px';
}

function fitMedia(scope){
  (scope || document).querySelectorAll('.media-box.ar').forEach(fitBox);
}

/* One observer for every slot; fires when a slide becomes visible and gains a
   size, which is exactly when the first fit becomes possible. */
const fitObserver = (typeof ResizeObserver !== 'undefined')
  ? new ResizeObserver(entries => {
      entries.forEach(e => {
        const box = e.target.querySelector('.media-box.ar');
        if(box) fitBox(box);
      });
    })
  : null;

const LAYOUTS = {
  /* ---- PowerPoint-equivalent layouts ---- */
  'title': s => {
    const t = textRegion({eyebrow:s.eyebrow, heading:s.heading, headingLevel:1});
    if(s.subheading || s.byline){
      const b = el('div', 'byline');
      if(s.subheading) b.appendChild(el('strong', null, s.subheading));
      if(s.byline) b.appendChild(el('span', null, s.byline));
      t.appendChild(b);
    }
    return [t];
  },
  'title-only': s => [textRegion({eyebrow:s.eyebrow, heading:s.heading, headingLevel:1})],
  'title-content': s => [textRegion(s)],
  'section': s => {
    const t = textRegion({eyebrow:s.eyebrow, heading:s.heading, headingLevel:1});
    t.insertBefore(el('div','rule'), t.querySelector('h1') ? t.querySelector('h1').nextSibling : null);
    if(s.subheading) t.appendChild(el('div','subhead', s.subheading));
    if(s.body) t.appendChild(el('div', null, s.body));
    return [t];
  },
  'two-content': s => {
    const head = (s.heading || s.eyebrow) ? textRegion({eyebrow:s.eyebrow, heading:s.heading}) : null;
    const cols = el('div', 'cols top');
    ['left','right'].forEach(side => {
      const blk = s[side] || {};
      const m = pickMedia(blk);
      cols.appendChild(m ? figure(m, {aspect: blk.aspect}) : textRegion(blk));
    });
    return withCallout(head ? [head, cols] : [cols], s);
  },
  'comparison': s => {
    const out = [];
    if(s.heading || s.eyebrow) out.push(textRegion({eyebrow:s.eyebrow, heading:s.heading}));
    const cols = el('div', 'cols top');
    ['left','right'].forEach(side => {
      const blk = Object.assign({}, s[side] || {});
      const m = pickMedia(blk);
      const region = el('div', 'region stack');
      if(blk.subheading) region.appendChild(el('h3', null, blk.subheading));
      /* The subheading is already the column's h3; don't print it twice. */
      region.appendChild(m ? figure(m, {aspect: blk.aspect})
                           : textRegion(Object.assign({}, blk, {subheading: null})));
      cols.appendChild(region);
    });
    out.push(cols);
    return withCallout(out, s);
  },
  'content-caption': s => {
    const cols = el('div', 'cols wide-media');
    const m = pickMedia(s);
    if(m){
      const f = figure(m, {aspect: s.aspect});
      f.classList.add('media-region');
      cols.appendChild(f);
    } else {
      cols.appendChild(textRegion({body:s.body, bullets:s.bullets}));
    }
    cols.appendChild(textRegion({eyebrow:s.eyebrow, heading:s.heading, subheading:s.subheading, body:s.caption, callout:s.callout}));
    return [cols];
  },
  'picture-caption': s => {
    const m = pickMedia(s);
    const wrap = el('div', 'region stack center' + (m ? ' has-media' : ''));
    if(s.heading) wrap.appendChild(el('h2', null, s.heading));
    if(m) wrap.appendChild(figure(m, {aspect: s.aspect}));
    if(s.body) wrap.appendChild(el('div', 'caption', s.body));
    return [wrap];
  },

  /* ---- media layouts ---- */
  'media-right': s => splitMedia(s, 'right'),
  'media-left':  s => splitMedia(s, 'left'),
  'media-caption': s => {
    const m = pickMedia(s);
    const wrap = el('div', 'region stack' + (m ? ' has-media' : ''));
    if(s.eyebrow) wrap.appendChild(el('div','eyebrow', s.eyebrow));
    if(s.heading) wrap.appendChild(el('h2', null, s.heading));
    if(m) wrap.appendChild(figure(m, {aspect: s.aspect}));
    return [wrap];
  },
  'media-full': s => {
    const m = pickMedia(s);
    const out = [];
    /* Full-bleed fills the slide by definition, so it never holds a ratio —
       the image crops with object-fit and an embed takes the whole screen. */
    if(m) out.push(mediaBox(m, {fit:'cover', aspect:'auto', force:true}));
    if(s.heading || s.body || s.eyebrow){
      const scrim = ['bottom','left','none'].includes(s.scrim) ? s.scrim : 'bottom';
      const ov = el('div', 'overlay scrim-' + scrim);
      if(s.eyebrow) ov.appendChild(el('div','eyebrow', s.eyebrow));
      /* A full-bleed slide is a cover or a chapter opener: its heading is the
         biggest thing on screen, and the page's top-level heading. */
      if(s.heading) ov.appendChild(el('h1', null, s.heading));
      if(s.body) ov.appendChild(el('div', 'body', s.body));
      out.push(ov);
    }
    return out;
  },
  'cards': s => {
    const out = [];
    if(s.eyebrow || s.heading || s.subheading || s.body){
      out.push(textRegion({eyebrow:s.eyebrow, heading:s.heading, subheading:s.subheading, body:s.body}));
    }
    out.push(cardList(s.cards, !!s.numbered));
    return withCallout(out, s);
  },
  'quote': s => {
    const out = [];
    if(s.eyebrow || s.heading) out.push(textRegion({eyebrow:s.eyebrow, heading:s.heading}));
    const cols = el('div', 'cols quote-cols');
    if(s.quote) cols.appendChild(pullQuote(s.quote, s.cite, true));
    const m = pickMedia(s);
    if(m){
      const f = figure(m, {aspect: s.aspect});
      f.classList.add('media-region');
      cols.appendChild(f);
    } else if(s.subheading || s.body || (s.bullets && s.bullets.length)){
      const side = el('div', 'side-panel');
      if(s.subheading) side.appendChild(el('h3', null, s.subheading));
      if(s.body) side.appendChild(el('div', 'body', s.body));
      if(s.bullets && s.bullets.length) side.appendChild(bulletList(s.bullets));
      cols.appendChild(side);
    } else {
      cols.classList.add('top');
    }
    out.push(cols);
    return withCallout(out, s);
  },
  'grid': s => {
    const items = (s.images || []).map(i => Object.assign({kind:'image'}, i));
    const out = [];
    if(s.heading || s.eyebrow) out.push(textRegion({eyebrow:s.eyebrow, heading:s.heading}));
    const g = el('div', 'grid n' + Math.min(4, Math.max(2, items.length)));
    items.forEach(i => g.appendChild(figure(i, {fit:'cover', aspect: s.aspect || 'auto'})));
    out.push(g);
    return out;
  },
  'quad-chart': s => {
    const out = [];
    if(s.heading || s.eyebrow || s.subheading) out.push(textRegion({eyebrow:s.eyebrow, heading:s.heading, subheading:s.subheading}));
    const grid = el('div', 'quad-chart');
    (s.quads || []).forEach(quad => {
      const card = el('div', 'quad-card');
      const media = pickMedia(quad);
      card.appendChild(textRegion({subheading: quad.subheading, body: quad.body, bullets: quad.bullets}));
      if(media) card.appendChild(figure(media, {aspect: quad.aspect || s.aspect || 'auto', fit:'cover'}));
      grid.appendChild(card);
    });
    out.push(grid);
    return withCallout(out, s);
  }
};

/* Layouts whose text region is not textRegion(s) add the callout here, as
   the last thing on the slide. */
function withCallout(nodes, s){
  if(s.callout) nodes.push(callout(s.callout));
  return nodes;
}

function splitMedia(s, side){
  const cols = el('div', 'cols wide-media');
  const m = pickMedia(s);
  const text = textRegion(s);
  const media = m ? figure(m, {aspect: s.aspect}) : el('div','region');
  media.classList.add('media-region');
  if(side === 'left'){ cols.appendChild(media); cols.appendChild(text); }
  else { cols.appendChild(text); cols.appendChild(media); }
  return [cols];
}

function buildSlide(s, n){
  const layout = s.layout || 'blank';
  const d = el('div', 'slide ' + (s.cls || ''));
  d.dataset.layout = layout;

  if(layout === 'blank' || !LAYOUTS[layout]){
    // Legacy / freeform slides: raw markup, exactly as before.
    d.innerHTML = s.html || '';
  } else {
    d.classList.add('lay');
    if(layout === 'media-full') d.classList.add('bleed');
    if(layout === 'section') d.classList.add('section-head');
    LAYOUTS[layout](s).forEach(node => d.appendChild(node));
  }

  if(s.tag){
    d.classList.add('has-tag');
    d.insertBefore(el('div', 'tag', s.tag), d.firstChild);
  }
  if(s.source){
    d.classList.add('has-source');
    d.appendChild(el('footer', 'source', s.source));
  }
  const num = el('div', 'num', (n + 1) + ' / ' + SLIDES.length);
  num.setAttribute('aria-hidden', 'true');   // the slide's own label says it
  d.appendChild(num);

  /* Each slide is a labelled group ("slide, 3 of 6: heading"); inactive
     slides are display:none, so assistive tech only ever meets the current
     one. */
  d.setAttribute('role', 'group');
  d.setAttribute('aria-roledescription', 'slide');
  d.setAttribute('aria-label', slideLabel(s, n));
  return d;
}

function plainText(html){
  const t = document.createElement('div');
  t.innerHTML = html || '';
  return (t.textContent || '').replace(/\s+/g, ' ').trim();
}
function slideLabel(s, n){
  const name = plainText(s.heading) || s.title || '';
  return (n + 1) + ' of ' + SLIDES.length + (name ? ': ' + name : '');
}

SLIDES.forEach((s, n) => stage.appendChild(buildSlide(s, n)));
const els = stage.querySelectorAll('.slide');
if(fitObserver) stage.querySelectorAll('.fitslot').forEach(sl => fitObserver.observe(sl));
window.addEventListener('resize', () => fitMedia(els[i]));

/* ---- embed lifecycle ----
   Every slide lives in the DOM at once, so an iframe left mounted would keep
   a YouTube video playing (and audible) after you advance. Embeds are
   therefore created when their slide becomes active and destroyed when it
   stops being active — removing the element is what actually stops playback.
   It also means a deck with a dozen embeds loads nothing until it needs to. */

function mountEmbeds(slideEl){
  slideEl.querySelectorAll('[data-embed]').forEach(box => {
    if(box.querySelector('iframe')) return;
    const spec = EMBEDS.get(box);
    if(!spec) return;

    const frame = document.createElement('iframe');
    frame.setAttribute('allowfullscreen', '');
    frame.setAttribute('loading', 'eager');
    frame.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
    if(spec.allow) frame.setAttribute('allow', spec.allow);
    else if(spec.external) frame.setAttribute('allow',
      'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen');

    const fb = box.querySelector('.embed-fallback');
    if(fb) fb.classList.remove('on');

    if(spec.srcdoc != null){
      /* Self-contained activity. Scripts yes, same-origin no — it can run its
         own game code but cannot reach into the deck. */
      frame.setAttribute('sandbox', spec.sandbox || 'allow-scripts allow-popups allow-forms allow-modals');
      frame.srcdoc = spec.srcdoc;
    } else if(spec.src){
      if(spec.sandbox) frame.setAttribute('sandbox', spec.sandbox);
      let timer = setTimeout(() => { if(fb) fb.classList.add('on'); }, spec.timeout || 6000);
      frame.addEventListener('load', () => clearTimeout(timer));
      frame.addEventListener('error', () => { clearTimeout(timer); if(fb) fb.classList.add('on'); });
      // A known-offline browser shouldn't sit staring at a blank frame.
      if(navigator.onLine === false && fb){ clearTimeout(timer); fb.classList.add('on'); }
      frame.src = spec.src;
    } else {
      if(fb) fb.classList.add('on');
      return;
    }
    box.appendChild(frame);
  });
}

function unmountEmbeds(slideEl){
  slideEl.querySelectorAll('[data-embed] iframe').forEach(f => f.remove());
}

function retryEmbeds(){
  const cur = els[i];
  if(!cur) return;
  unmountEmbeds(cur);
  cur.querySelectorAll('.embed-fallback').forEach(f => f.classList.remove('on'));
  mountEmbeds(cur);
}

function render(n){
  const prev = i;
  i = Math.max(0, Math.min(SLIDES.length - 1, n));
  els.forEach((e, k) => e.classList.toggle('active', k === i));
  if(els[prev] && prev !== i) unmountEmbeds(els[prev]);
  if(els[i]){ mountEmbeds(els[i]); fitMedia(els[i]); }
  notesEl.innerHTML = SLIDES[i].notes || '<i>No notes for this slide.</i>';
  if(prev !== i || !announced){
    announced = true;
    document.getElementById('announce').textContent = 'Slide ' + slideLabel(SLIDES[i], i);
  }
  if(!LIVE) location.hash = i + 1;
}
let announced = false;
function setNotes(on){
  notesOn = !!on;
  notesEl.classList.toggle('on', notesOn);
  document.body.classList.toggle('notes-on', notesOn);
  /* Measure rather than assume: the panel's height depends on how long the
     notes for this slide are. */
  document.documentElement.style.setProperty(
    '--notes-h', notesOn ? notesEl.offsetHeight + 'px' : '0px');
  requestAnimationFrame(() => fitMedia(els[i]));
}

function setBlank(on){
  blanked = !!on;
  blankEl.classList.toggle('on', blanked);
}

function liveNotesHTML(text){
  const raw = String(text || '');
  if(!raw.trim()) return '<p class="ln-empty">No live notes yet for this slide.</p>';
  const escaped = raw.replace(/[&<>]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[ch]));
  return '<div class="ln-text">' + escaped + '</div>';
}
function setLiveNotes(text, visible){
  if(typeof text === 'string') liveNoteText = text;
  if(typeof visible === 'boolean') liveNotesVisible = visible;
  liveNotesBodyEl.innerHTML = liveNotesHTML(liveNoteText);
  liveNotesStateEl.textContent = 'Slide ' + (i + 1) + (liveNoteText ? ' · autosaved' : '');
  liveNotesEl.classList.toggle('on', !!liveNotesVisible && !!liveNoteText.trim());
}

/* --- text size -------------------------------------------------------- */

let toastTimer = null;
function toast(big, small){
  document.getElementById('scaleval').textContent = big;
  toastEl.querySelector('span').textContent = small;
  toastEl.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('on'), small === 'text size' ? 900 : 2600);
}

function applyScale(v, announce){
  const num = parseFloat(v);
  /* A server predating this feature sends no `scale`, and NaN here would
     poison every calc() in the stylesheet -- the whole deck would collapse to
     default font sizes. Keep the current value instead. */
  if(!isFinite(num)) return;
  scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.round(num * 100) / 100));
  document.documentElement.style.setProperty('--scale', scale);
  requestAnimationFrame(() => fitMedia(els[i]));
  if(!LIVE) try{ localStorage.setItem('deckScale', scale); }catch(e){}
  if(announce) toast(Math.round(scale * 100) + '%', 'text size');
}

/* In live mode the server owns the value, same as the slide index, so the
   phone's readout always matches what's on the wall. If the server can't take
   the request -- most likely it was started before this feature existed --
   fall back to resizing just this screen and say so, rather than appearing to
   do nothing. */
function requestScale(body, localValue){
  if(!LIVE){ applyScale(localValue, true); return; }
  post('/api/scale', body).then(r => {
    if(r.ok) return;
    applyScale(localValue, false);
    toast(Math.round(scale * 100) + '%',
          r.status === 404 ? 'this screen only — restart the server to sync'
                           : 'this screen only — server unreachable');
  });
}
function bumpScale(steps){ requestScale({step: steps}, scale + steps * SCALE_STEP); }
function resetScale(){ requestScale({scale: 1}, 1); }

/* --- themes ----------------------------------------------------------- */

function findTheme(id){
  for(const t of THEMES) if(t.id === id) return t;
  return THEMES[0] || null;
}
/* Writes the theme's tokens onto :root. Every colour and face in the
   stylesheet reads from these, so this one call restyles the deck. Tokens
   the previous theme set and this one doesn't are cleared, so they fall back
   to the stylesheet's defaults instead of leaking across themes. */
let appliedThemeKeys = [];
function applyTheme(id, announce){
  const t = findTheme(id);
  if(!t) return;
  themeId = t.id;
  const root = document.documentElement.style;
  const vars = t.vars || {};
  for(const key of appliedThemeKeys) if(!(key in vars)) root.removeProperty(key);
  for(const key in vars) root.setProperty(key, vars[key]);
  appliedThemeKeys = Object.keys(vars);
  if(!LIVE && announce) try{
    localStorage.setItem('deckTheme', themeId);
    localStorage.setItem('deckTheme:' + DECK_TITLE, themeId);
  }catch(e){}
  if(announce) toast(t.name, 'theme');
}
function requestTheme(id, announceLocally){
  if(!LIVE){ applyTheme(id, true); return; }
  post('/api/theme', {id: id}).then(r => {
    if(r.ok) return;
    applyTheme(id, false);
    toast(findTheme(id).name,
          r.status === 404 ? 'this screen only — restart the server to sync'
                           : 'this screen only — server unreachable');
  });
}
function cycleTheme(){
  if(THEMES.length < 2) return;
  let idx = THEMES.findIndex(t => t.id === themeId);
  requestTheme(THEMES[(idx + 1 + THEMES.length) % THEMES.length].id);
}

/* --- deck switcher ---------------------------------------------------- */

function renderDeckPickerList(){
  dpListEl.innerHTML = '';
  const esc = s => String(s || '').replace(/[&<>]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[ch]));
  DECKS.forEach((d, idx) => {
    const isCurrent = d.id === currentDeckId;
    const isFocused = idx === dpFocusedIdx;
    const item = document.createElement('div');
    item.className = 'dp-item' + (isCurrent ? ' active' : '') + (isFocused ? ' focused' : '');
    item.id = 'dp-opt-' + idx;
    item.setAttribute('role', 'option');
    item.setAttribute('aria-selected', isFocused ? 'true' : 'false');
    if(isCurrent) item.setAttribute('aria-current', 'true');
    item.dataset.id = d.id;
    item.dataset.index = idx;

    const num = idx < 9 ? (idx + 1) : '';
    const keyHtml = num ? '<span class="dp-key">' + num + '</span>' : '';
    const badgeHtml = isCurrent ? '<span class="dp-badge">Current</span>' : '';
    const descHtml = d.subtitle ? '<div class="dp-desc">' + esc(d.subtitle) + '</div>' : '';

    item.innerHTML = keyHtml +
      '<div class="dp-info">' +
        '<div class="dp-name">' + esc(d.title || d.id) + badgeHtml + '</div>' +
        descHtml +
      '</div>' +
      '<span class="dp-count">' + (d.count || 0) + ' slides</span>';

    item.addEventListener('click', () => {
      selectDeck(d.id);
    });
    dpListEl.appendChild(item);
  });

  const focusedItem = dpListEl.querySelector('.dp-item.focused');
  if(focusedItem){
    dpListEl.setAttribute('aria-activedescendant', focusedItem.id);
    if(focusedItem.scrollIntoView) focusedItem.scrollIntoView({block: 'nearest'});
  }
}

function openDeckPicker(){
  if(!LIVE){
    toast('Live only', 'deck switching requires server');
    return;
  }
  if(!DECKS || DECKS.length < 2){
    const name = DECKS && DECKS[0] ? (DECKS[0].title || DECKS[0].id) : '1 deck';
    toast(name, 'only deck in project');
    return;
  }
  deckPickerOpen = true;
  const curIdx = DECKS.findIndex(d => d.id === currentDeckId);
  dpFocusedIdx = curIdx >= 0 ? curIdx : 0;
  renderDeckPickerList();
  /* Move focus into the dialog, and remember where it came from so closing
     puts the keyboard user back where they were. */
  dpReturnFocus = document.activeElement;
  deckPickerEl.classList.add('on');
  dpListEl.focus();
}

let dpReturnFocus = null;
function closeDeckPicker(){
  deckPickerOpen = false;
  deckPickerEl.classList.remove('on');
  if(dpReturnFocus && dpReturnFocus.focus && document.contains(dpReturnFocus)) dpReturnFocus.focus();
  dpReturnFocus = null;
}

function selectDeck(deckId){
  if(deckId === currentDeckId){
    closeDeckPicker();
    return;
  }
  closeDeckPicker();
  post('/api/deck', {id: deckId}).then(r => {
    if(!r.ok){
      toast('Failed', 'could not switch deck');
    }
  });
}

function handleDeckPickerKey(e){
  const k = e.key;
  if(k === 'Escape' || k === 'd' || k === 'D'){
    e.preventDefault();
    closeDeckPicker();
    return;
  }
  if(k === 'ArrowDown' || k === 'j' || k === 'Tab'){
    e.preventDefault();
    dpFocusedIdx = (dpFocusedIdx + 1) % DECKS.length;
    renderDeckPickerList();
    return;
  }
  if(k === 'ArrowUp' || k === 'k'){
    e.preventDefault();
    dpFocusedIdx = (dpFocusedIdx - 1 + DECKS.length) % DECKS.length;
    renderDeckPickerList();
    return;
  }
  if(k === 'Enter'){
    e.preventDefault();
    if(DECKS[dpFocusedIdx]){
      selectDeck(DECKS[dpFocusedIdx].id);
    }
    return;
  }
  if(/^[1-9]$/.test(k)){
    const num = parseInt(k, 10);
    if(num >= 1 && num <= DECKS.length){
      e.preventDefault();
      selectDeck(DECKS[num - 1].id);
      return;
    }
  }
}

deckPickerEl.addEventListener('click', e => {
  if(e.target === deckPickerEl){
    closeDeckPicker();
  }
});

/* In live mode the server owns the slide index, so navigation is a request,
   not a local change — that keeps the projector and the phone in step. */
function go(n){
  if(LIVE){ post('/api/goto', {n: n + 1}); }
  else { render(n); }
}
/* Reports whether the request actually landed. fetch() resolves normally on a
   404, so `ok` has to be checked explicitly — silently swallowing that is how
   a stale server looks identical to a broken feature. */
/* A projector on another machine is a remote like any other: it needs the
   key from the link `glissade start` printed. On this machine it doesn't. */
const CONTROL_KEY = new URLSearchParams(location.search).get('k') || '';
function post(path, body){
  const headers = {'Content-Type': 'application/json'};
  if(CONTROL_KEY) headers['X-Glissade-Key'] = CONTROL_KEY;
  return fetch(path, {
    method: 'POST',
    headers: headers,
    body: JSON.stringify(body || {})
  }).then(r => ({ok: r.ok, status: r.status}))
    .catch(() => ({ok: false, status: 0}));
}

document.addEventListener('keydown', e => {
  if(deckPickerOpen){
    handleDeckPickerKey(e);
    return;
  }
  const k = e.key;
  if(k === 'ArrowRight' || k === 'ArrowDown' || k === ' ' || k === 'PageDown'){ e.preventDefault(); go(i + 1); }
  else if(k === 'ArrowLeft' || k === 'ArrowUp' || k === 'PageUp'){ e.preventDefault(); go(i - 1); }
  else if(k === 'Home'){ go(0); }
  else if(k === 'End'){ go(SLIDES.length - 1); }
  else if(k === 'n' || k === 'N'){ setNotes(!notesOn); }
  else if(k === 'b' || k === 'B'){ LIVE ? post('/api/blank', {blank: !blanked}) : setBlank(!blanked); }
  else if(k === 'd' || k === 'D'){ openDeckPicker(); }
  /* '=' is the unshifted key on most layouts, so + works without Shift. */
  else if(k === '+' || k === '=' || k === 'Add'){ e.preventDefault(); bumpScale(1); }
  else if(k === '-' || k === '_' || k === 'Subtract'){ e.preventDefault(); bumpScale(-1); }
  else if(k === '0'){ e.preventDefault(); resetScale(); }
  else if(k === 't' || k === 'T'){ cycleTheme(); }
  else if(k === 'l' || k === 'L'){ if(LIVE) post('/api/live-notes-visible', {visible: !liveNotesVisible}); }
  else if(k === 'r' || k === 'R'){ retryEmbeds(); }
  else if(k === '?' || k === 'h' || k === 'H'){ toggleHelp(); }
  else if(k === 'Escape' && helpEl.classList.contains('on')){ toggleHelp(); }
  else if(k === 'f' || k === 'F'){
    if(!document.fullscreenElement) document.documentElement.requestFullscreen && document.documentElement.requestFullscreen();
    else document.exitFullscreen && document.exitFullscreen();
  }
});
stage.addEventListener('click', e => {
  if(deckPickerOpen) return;
  go(e.clientX < window.innerWidth * 0.25 ? i - 1 : i + 1);
});

if(LIVE){
  liveEl.classList.add('show');
  let es, first = true, rev = null;
  const connect = () => {
    es = new EventSource('/events');
    es.onopen = () => {
      liveEl.classList.add('ok');
      liveEl.querySelector('span').textContent = 'remote connected';
    };
    es.onmessage = ev => {
      const st = JSON.parse(ev.data);
      if(st.deck != null) currentDeckId = st.deck;
      /* The slides were baked into this page when it was served, so a deck
         change means the page itself is stale — reload rather than trying to
         swap 20 slides in place. */
      if(st.rev != null){
        if(rev == null) rev = st.rev;
        else if(st.rev !== rev){ location.reload(); return; }
      }
      const sizeChanged = st.scale != null && st.scale !== scale;
      const themeChanged = st.theme != null && st.theme !== themeId;
      render(st.n - 1);
      setBlank(st.blank);
      setLiveNotes(st.live_note || '', !!st.live_notes_visible);
      applyScale(st.scale, sizeChanged && !first && !themeChanged);
      if(st.theme != null) applyTheme(st.theme, themeChanged && !first);
      first = false;
    };
    es.onerror = () => {
      liveEl.classList.remove('ok');
      liveEl.querySelector('span').textContent = 'reconnecting…';
      es.close();
      setTimeout(connect, 1500);
    };
  };
  connect();
  render(0);
} else {
  /* Standalone: no server to remember anything, so the browser does. */
  /* A deck that names its theme opens in it; a theme the viewer picked with
     T for this deck is remembered and wins after that. */
  let saved = 1, savedTheme = null;
  try{
    saved = parseFloat(localStorage.getItem('deckScale')) || 1;
    savedTheme = localStorage.getItem('deckTheme:' + DECK_TITLE)
      || (DECK_THEME ? null : localStorage.getItem('deckTheme'));
  }catch(e){}
  applyScale(saved, false);
  applyTheme(savedTheme || DECK_THEME || themeId, false);
  const start = parseInt(location.hash.replace('#',''), 10);
  render(isNaN(start) ? 0 : start - 1);
}
