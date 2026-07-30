// Glissade Landing Page Interactive Script

document.addEventListener('DOMContentLoaded', () => {
  initInstallTabs();
  initCopyButton();
  initSimulator();
  initLayoutCatalogue();
});

/* -------------------------------------------------------------------------- */
/* Install Command Tabs & Copy                                                */
/* -------------------------------------------------------------------------- */
const COMMANDS = {
  uv: 'uv tool install --from git+https://github.com/techmuch/glissade glissade',
  pipx: 'pipx install git+https://github.com/techmuch/glissade.git',
  pip: 'pip install git+https://github.com/techmuch/glissade.git',
  uvx: 'uvx --from git+https://github.com/techmuch/glissade glissade demo'
};

function initInstallTabs() {
  const tabs = document.querySelectorAll('#installTabs .tab-btn');
  const codeEl = document.getElementById('installCommand');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const tool = tab.getAttribute('data-tool');
      if (COMMANDS[tool]) {
        codeEl.textContent = COMMANDS[tool];
      }
    });
  });
}

function initCopyButton() {
  const copyBtn = document.getElementById('copyInstallBtn');
  const codeEl = document.getElementById('installCommand');
  const copyText = copyBtn.querySelector('.copy-text');

  copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(codeEl.textContent).then(() => {
      copyText.textContent = 'Copied!';
      copyBtn.style.borderColor = 'var(--accent-emerald)';
      copyBtn.style.color = 'var(--accent-emerald)';
      setTimeout(() => {
        copyText.textContent = 'Copy';
        copyBtn.style.borderColor = '';
        copyBtn.style.color = '';
      }, 2000);
    });
  });
}

/* -------------------------------------------------------------------------- */
/* Interactive Simulator                                                     */
/* -------------------------------------------------------------------------- */
const DEMO_SLIDES = [
  {
    title: 'Introducing Glissade',
    eyebrow: 'OVERVIEW',
    heading: 'Presentation Decks Written in JSON',
    body: '<p>Built into a single HTML file that works when the Wi-Fi doesn\'t. No compilers, pure Python.</p>',
    notes: 'Welcome everyone. Start by running `glissade demo` to show how fast it works.'
  },
  {
    title: 'Phone Remote Sync',
    eyebrow: 'WI-FI CONTROL',
    heading: 'Scan QR & Control From Your Phone',
    body: '<p>Both devices connect on the same Wi-Fi. Advances slides, previews upcoming slides, and captures live audience notes.</p>',
    notes: 'Emphasize that the phone connects directly over the local network — zero external cloud servers required.'
  },
  {
    title: 'Zero-Wi-Fi Single File Build',
    eyebrow: 'OFFLINE FIRST',
    heading: 'Build The Night Before',
    body: '<p><code>glissade build</code> inlines images, fonts, and stylesheets into one single HTML file. No missing folder to forget.</p>',
    notes: 'Point out the optional `glissade[images]` feature which automatically downscales heavy images.'
  },
  {
    title: 'AI Agent Workflows',
    eyebrow: 'PROMPTING',
    heading: 'AGENTS.md & Schema Validation',
    body: '<p>Point Claude, Cursor, or Antigravity at your project and let them generate complete, schema-valid talks automatically.</p>',
    notes: 'Remind the audience to run `glissade check --fix` after AI finishes writing slides.'
  }
];

let currentSlideIdx = 0;
const THEMES = [
  { id: 'paper', name: 'Paper', class: 'theme-paper' },
  { id: 'dark', name: 'Dark', class: 'theme-dark' },
  { id: 'gt', name: 'Georgia Tech', class: 'theme-gt' }
];
let currentThemeIdx = 0;

function initSimulator() {
  const display = document.getElementById('currentSlideDisplay');
  const slideNumEl = document.getElementById('currentSlideNum');
  const totalNumEl = document.getElementById('totalSlideNum');
  const remoteTitleEl = document.getElementById('remoteSlideTitle');
  const remoteNotesEl = document.getElementById('remoteSpeakerNotes');
  
  const prevBtn = document.getElementById('prevSlideBtn');
  const nextBtn = document.getElementById('nextSlideBtn');
  const blankBtn = document.getElementById('blankScreenBtn');
  
  const toggleNotesBtn = document.getElementById('toggleNotesBtn');
  const notesPanel = document.getElementById('speakerNotesPanel');
  const notesText = document.getElementById('speakerNotesText');

  const toggleOverlayBtn = document.getElementById('toggleLiveOverlayBtn');
  const overlayDisplay = document.getElementById('liveOverlayDisplay');
  const overlayText = document.getElementById('overlayText');
  const liveInput = document.getElementById('liveNotesInput');

  const cycleThemeBtn = document.getElementById('cycleThemeBtn');
  const themeNameEl = document.getElementById('themeName');
  const screenEl = document.getElementById('projectorDisplay');

  totalNumEl.textContent = DEMO_SLIDES.length;

  function renderSlide(index) {
    const slide = DEMO_SLIDES[index];
    slideNumEl.textContent = index + 1;
    remoteTitleEl.textContent = slide.title;
    remoteNotesEl.textContent = slide.notes;
    notesText.textContent = slide.notes;

    display.innerHTML = `
      <div class="slide-eyebrow">${slide.eyebrow}</div>
      <h2 class="slide-heading">${slide.heading}</h2>
      <div class="slide-body">${slide.body}</div>
    `;
  }

  prevBtn.addEventListener('click', () => {
    currentSlideIdx = (currentSlideIdx - 1 + DEMO_SLIDES.length) % DEMO_SLIDES.length;
    renderSlide(currentSlideIdx);
  });

  nextBtn.addEventListener('click', () => {
    currentSlideIdx = (currentSlideIdx + 1) % DEMO_SLIDES.length;
    renderSlide(currentSlideIdx);
  });

  blankBtn.addEventListener('click', () => {
    if (display.style.opacity === '0') {
      display.style.opacity = '1';
      blankBtn.style.background = '';
    } else {
      display.style.opacity = '0';
      blankBtn.style.background = 'var(--accent-rose)';
    }
  });

  toggleNotesBtn.addEventListener('click', () => {
    notesPanel.classList.toggle('hidden');
  });

  toggleOverlayBtn.addEventListener('click', () => {
    overlayDisplay.classList.toggle('hidden');
  });

  liveInput.addEventListener('input', (e) => {
    const text = e.target.value.trim();
    if (text) {
      overlayText.textContent = text;
      overlayDisplay.classList.remove('hidden');
    } else {
      overlayText.textContent = 'Q: Can we customize fonts? A: Yes via themes.json!';
    }
  });

  cycleThemeBtn.addEventListener('click', () => {
    screenEl.classList.remove(THEMES[currentThemeIdx].class);
    currentThemeIdx = (currentThemeIdx + 1) % THEMES.length;
    const theme = THEMES[currentThemeIdx];
    screenEl.classList.add(theme.class);
    themeNameEl.textContent = theme.name;
  });

  // Initial render
  renderSlide(0);
}

/* -------------------------------------------------------------------------- */
/* Layout Catalogue Interactive Viewer                                        */
/* -------------------------------------------------------------------------- */
const LAYOUT_DATA = {
  title: {
    json: `{
  "title": "Glissade Launch",
  "layout": "title",
  "eyebrow": "RELEASE 0.9.0",
  "heading": "Presentation decks written as JSON",
  "subheading": "Driven from your phone",
  "notes": "Introduce the core philosophy of Glissade."
}`,
    html: `
      <div class="slide-eyebrow">RELEASE 0.9.0</div>
      <h2 class="slide-heading" style="font-size: 2rem;">Presentation decks written as JSON</h2>
      <p style="color: #666; font-size: 1.1rem;">Driven from your phone</p>
    `
  },
  'media-right': {
    json: `{
  "title": "Architecture Overview",
  "layout": "media-right",
  "eyebrow": "SYSTEM",
  "heading": "Local FastAPI + Phone Sync",
  "body": "<p>Server holds slide position; clients auto-sync via WebSockets.</p>",
  "image": { "src": "media/diagram.png", "alt": "System chart" }
}`,
    html: `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: center;">
        <div>
          <div class="slide-eyebrow">SYSTEM</div>
          <h3 style="font-size: 1.5rem; margin-bottom: 8px;">Local FastAPI + Phone Sync</h3>
          <p style="font-size: 0.9rem; color: #444;">Server holds slide position; clients auto-sync via WebSockets.</p>
        </div>
        <div style="background: #e2e8f0; height: 140px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-family: monospace; font-size: 0.8rem; color: #64748b;">
          [ media/diagram.png ]
        </div>
      </div>
    `
  },
  grid: {
    json: `{
  "title": "Feature Grid",
  "layout": "grid",
  "heading": "Three Pillars of Glissade",
  "grid": [
    { "heading": "Offline", "body": "Single HTML build" },
    { "heading": "Remote", "body": "Phone Wi-Fi sync" },
    { "heading": "AI Ready", "body": "AGENTS.md guided" }
  ]
}`,
    html: `
      <h3 style="font-size: 1.5rem; margin-bottom: 16px;">Three Pillars of Glissade</h3>
      <div class="slide-grid" style="grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
        <div class="grid-card"><strong>Offline</strong><p style="font-size: 0.85rem;">Single HTML build</p></div>
        <div class="grid-card"><strong>Remote</strong><p style="font-size: 0.85rem;">Phone Wi-Fi sync</p></div>
        <div class="grid-card"><strong>AI Ready</strong><p style="font-size: 0.85rem;">AGENTS.md guided</p></div>
      </div>
    `
  },
  'quad-chart': {
    json: `{
  "title": "Strategy Quad",
  "layout": "quad-chart",
  "heading": "2x2 Matrix Analysis",
  "quads": [
    { "title": "Q1: Growth", "body": "Core user features" },
    { "title": "Q2: Scale", "body": "Performance optimization" },
    { "title": "Q3: Retain", "body": "Developer docs & DX" },
    { "title": "Q4: Explore", "body": "AI-assisted workflows" }
  ]
}`,
    html: `
      <h3 style="font-size: 1.4rem; margin-bottom: 12px;">2x2 Matrix Analysis</h3>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
        <div class="grid-card"><strong>Q1: Growth</strong><p style="font-size: 0.8rem;">Core user features</p></div>
        <div class="grid-card"><strong>Q2: Scale</strong><p style="font-size: 0.8rem;">Performance optimization</p></div>
        <div class="grid-card"><strong>Q3: Retain</strong><p style="font-size: 0.8rem;">Developer docs & DX</p></div>
        <div class="grid-card"><strong>Q4: Explore</strong><p style="font-size: 0.8rem;">AI-assisted workflows</p></div>
      </div>
    `
  },
  comparison: {
    json: `{
  "title": "Comparison",
  "layout": "comparison",
  "heading": "Cloud vs Local",
  "columns": [
    { "title": "Cloud Slide Tools", "body": "Fails without Wi-Fi" },
    { "title": "Glissade", "body": "Self-contained HTML file" }
  ]
}`,
    html: `
      <h3 style="font-size: 1.5rem; margin-bottom: 16px;">Cloud vs Local</h3>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        <div style="background: rgba(239, 68, 68, 0.1); padding: 12px; border-radius: 6px; border-left: 3px solid #ef4444;">
          <strong>Cloud Slide Tools</strong>
          <p style="font-size: 0.85rem; color: #7f1d1d;">Fails when venue Wi-Fi drops.</p>
        </div>
        <div style="background: rgba(16, 185, 129, 0.1); padding: 12px; border-radius: 6px; border-left: 3px solid #10b981;">
          <strong>Glissade</strong>
          <p style="font-size: 0.85rem; color: #064e3b;">Single self-contained HTML file.</p>
        </div>
      </div>
    `
  },
  ask: {
    json: `{
  "title": "Q&A Session",
  "layout": "title",
  "cls": "ask",
  "heading": "Questions & Feedback?",
  "subheading": "Scan QR code to submit live notes"
}`,
    html: `
      <div style="background: #25303a; color: #fff; padding: 24px; border-radius: 12px; text-align: center;">
        <div style="color: #fbbf24; font-size: 0.8rem; font-weight: 700; margin-bottom: 4px;">Q & A</div>
        <h2 style="font-size: 1.8rem; font-weight: 800;">Questions & Feedback?</h2>
        <p style="color: #94a3b8; font-size: 0.9rem; margin-top: 8px;">Scan QR code on your phone to submit notes live</p>
      </div>
    `
  }
};

function initLayoutCatalogue() {
  const tabs = document.querySelectorAll('#layoutNav .layout-tab');
  const jsonCodeEl = document.getElementById('layoutJsonCode');
  const visualEl = document.getElementById('layoutVisualPreview');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const layoutKey = tab.getAttribute('data-layout');
      if (LAYOUT_DATA[layoutKey]) {
        jsonCodeEl.textContent = LAYOUT_DATA[layoutKey].json;
        visualEl.innerHTML = LAYOUT_DATA[layoutKey].html;
      }
    });
  });

  // Initial load
  visualEl.innerHTML = LAYOUT_DATA.title.html;
}
