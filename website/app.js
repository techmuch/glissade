// Glissade Landing Page Interactive Script

document.addEventListener('DOMContentLoaded', () => {
  initInstallTabs();
  initCopyButton();
  initWalkthrough();
  initAgentTabs();
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

function flashCopyState(copyBtn) {
  const copyText = copyBtn.querySelector('.copy-text');
  const prevText = copyText ? copyText.textContent : null;

  if (copyText) copyText.textContent = 'Copied!';
  copyBtn.style.borderColor = 'var(--accent-emerald)';
  copyBtn.style.color = 'var(--accent-emerald)';

  setTimeout(() => {
    if (copyText && prevText != null) copyText.textContent = prevText;
    copyBtn.style.borderColor = '';
    copyBtn.style.color = '';
  }, 2000);
}

function initCopyButton() {
  const copyBtn = document.getElementById('copyInstallBtn');
  const codeEl = document.getElementById('installCommand');
  if (!copyBtn || !codeEl) return;

  copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(codeEl.textContent).then(() => {
      flashCopyState(copyBtn);
    });
  });
}

/* -------------------------------------------------------------------------- */
/* First-Talk Walkthrough                                                     */
/* -------------------------------------------------------------------------- */
const WALKTHROUGH_STEPS = {
  install: {
    kicker: 'Step 1 · Install',
    title: 'Install Glissade',
    description: 'Start with a single command. No Node bundler, no browser extension, and no compiler toolchain.',
    command: 'uv tool install --from git+https://github.com/techmuch/glissade glissade',
    resultTitle: 'You get a CLI you can run from anywhere',
    badges: ['Cross-platform', 'Zero compiler setup'],
    details: [
      'Installs one command-line tool named glissade.',
      'Works well for macOS, Linux, and Windows developer workflows.',
      'Keeps the setup lightweight for people who just want to make a talk.'
    ],
    visual: `
      <div class="wt-mini-terminal">
        <div class="wt-mini-terminal-bar"><span></span><span></span><span></span></div>
        <div class="wt-mini-terminal-body">
          <div><span class="wt-prompt">$</span> uv tool install --from git+https://github.com/techmuch/glissade glissade</div>
          <div class="wt-success">Installed 1 executable: glissade</div>
          <div class="wt-dim"><span class="wt-prompt">$</span> glissade --version</div>
          <div class="wt-success">glissade 0.14.0</div>
        </div>
      </div>
    `
  },
  init: {
    kicker: 'Step 2 · Init',
    title: 'Scaffold your talk project',
    description: 'Glissade creates a real starting point: a sample deck, AI guidance, and the schema your editor can validate against.',
    command: 'mkdir my-talk && cd my-talk\nglissade init',
    resultTitle: 'Glissade creates the files you need',
    badges: ['Starter deck', 'AI-ready scaffold'],
    details: [
      'Creates decks/welcome.json so you can start from a working example.',
      'Adds AGENTS.md to guide AI tools toward valid slide JSON.',
      'Adds glissade.schema.json so editors can validate as you type.'
    ],
    visual: `
      <div class="wt-file-tree">
        <div class="wt-folder">my-talk/</div>
        <div class="wt-file">├── <strong>decks/</strong></div>
        <div class="wt-file wt-indent">└── welcome.json</div>
        <div class="wt-file">├── AGENTS.md</div>
        <div class="wt-file">└── glissade.schema.json</div>
      </div>
    `
  },
  start: {
    kicker: 'Step 3 · Start',
    title: 'Run the live presentation server',
    description: 'Open the deck on your laptop, then scan the QR code or visit the control page from your phone on the same Wi-Fi.',
    command: 'glissade start',
    resultTitle: 'One screen presents. Your phone becomes the remote.',
    badges: ['Phone remote', 'Speaker notes'],
    details: [
      'The projector view shows the current slide full-screen.',
      'The control view gives you next/prev, slide info, and notes.',
      'Both stay in sync over the local network without a cloud service.'
    ],
    visual: `
      <div class="wt-dual-preview">
        <div class="wt-projector">
          <div class="wt-caption">Projector</div>
          <div class="wt-slide-card">
            <div class="slide-eyebrow">LIVE SERVER</div>
            <h4>Talk is ready to present</h4>
            <p>Open on the laptop and scan the QR code for the remote.</p>
          </div>
        </div>
        <div class="wt-phone">
          <div class="wt-caption">Phone remote</div>
          <div class="wt-phone-card">
            <div class="wt-phone-dot">● connected</div>
            <div class="wt-phone-title">Welcome Slide</div>
            <div class="wt-phone-buttons">
              <span>Prev</span><span>Blank</span><span>Next</span>
            </div>
          </div>
        </div>
      </div>
    `
  },
  edit: {
    kicker: 'Step 4 · Edit',
    title: 'Edit JSON and reload instantly',
    description: 'Change the deck file while the server is running. Connected projector and control views update live without losing the current presentation context.',
    command: 'code decks/welcome.json\n# save your change while glissade start is still running',
    resultTitle: 'Your changes appear live on connected screens',
    badges: ['Watch mode', 'Live reload'],
    details: [
      'Great for rehearsing, iterating, or collaborating with AI tools.',
      'Projector and phone control both reflect the updated deck.',
      'Designed to keep last-known-good state if a temporary edit is invalid.'
    ],
    visual: `
      <div class="wt-diff-card">
        <div class="wt-diff-side">
          <div class="wt-diff-label">Before</div>
          <code>"heading": "Welcome to Glissade"</code>
        </div>
        <div class="wt-diff-arrow">→</div>
        <div class="wt-diff-side wt-diff-side-active">
          <div class="wt-diff-label">After save</div>
          <code>"heading": "Updated from watch mode"</code>
        </div>
        <div class="wt-live-pill">Live updated</div>
      </div>
    `
  },
  build: {
    kicker: 'Step 5 · Build',
    title: 'Export one standalone HTML file',
    description: 'When the talk is ready, build a single self-contained HTML artifact you can open offline, email to yourself, or put on a thumb drive.',
    command: 'glissade build',
    resultTitle: 'You end up with one portable deck file',
    badges: ['Offline-ready', 'Single HTML output'],
    details: [
      'Build output goes into build/ with all required assets inlined.',
      'Useful for venues, backups, and situations where Wi-Fi is unreliable.',
      'This is the artifact you can safely carry to the event.'
    ],
    visual: `
      <div class="wt-artifact-card">
        <div class="wt-folder">build/</div>
        <div class="wt-artifact-file">talk.html</div>
        <div class="wt-artifact-note">Open locally. Present offline. No missing asset folder.</div>
      </div>
    `
  }
};

function initWalkthrough() {
  const stepButtons = document.querySelectorAll('#walkthroughSteps .walkthrough-step');
  const kickerEl = document.getElementById('walkthroughKicker');
  const titleEl = document.getElementById('walkthroughTitle');
  const descriptionEl = document.getElementById('walkthroughDescription');
  const badgesEl = document.getElementById('walkthroughBadges');
  const commandEl = document.getElementById('walkthroughCommand');
  const resultTitleEl = document.getElementById('walkthroughResultTitle');
  const visualEl = document.getElementById('walkthroughVisual');
  const detailsEl = document.getElementById('walkthroughDetails');
  const copyBtn = document.getElementById('copyWalkthroughBtn');

  if (!stepButtons.length) return;

  function renderStep(key) {
    const step = WALKTHROUGH_STEPS[key];
    if (!step) return;

    stepButtons.forEach(btn => {
      const isActive = btn.getAttribute('data-step') === key;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-pressed', String(isActive));
    });

    kickerEl.textContent = step.kicker;
    titleEl.textContent = step.title;
    descriptionEl.textContent = step.description;
    commandEl.textContent = step.command;
    resultTitleEl.textContent = step.resultTitle;
    visualEl.innerHTML = step.visual;
    badgesEl.innerHTML = step.badges.map(label => `<span class="walkthrough-badge">${label}</span>`).join('');
    detailsEl.innerHTML = step.details.map(item => `<li>${item}</li>`).join('');
  }

  stepButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      renderStep(btn.getAttribute('data-step'));
    });
  });

  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(commandEl.textContent).then(() => {
        flashCopyState(copyBtn);
      });
    });
  }

  renderStep('install');
}

/* -------------------------------------------------------------------------- */
/* Interactive Simulator                                                     */
/* -------------------------------------------------------------------------- */
const AGENT_PROMPTS = {
  claude: {
    context: 'Example workflow for Claude Code',
    prompt: '"Read <code>AGENTS.md</code> and create a 5-slide deck in <code>decks/talk.json</code> explaining why local-first software matters. Use the <code>media-right</code> layout for slide 2."',
    response: 'Checked <code>AGENTS.md</code>. Created <code>decks/talk.json</code> with 5 slides and verified structure with <code>glissade check</code> — 0 errors!'
  },
  antigravity: {
    context: 'Example workflow for Antigravity',
    prompt: '"Open this Glissade project, read <code>AGENTS.md</code>, and draft a concise 5-slide deck about local-first software. Keep the tone practical and put a visual on slide 2 with <code>media-right</code>."',
    response: 'Read the project guide, wrote <code>decks/talk.json</code>, preserved valid layouts, and left the deck ready for <code>glissade start</code>.'
  },
  opencode: {
    context: 'Example workflow for OpenCode',
    prompt: '"Use the repo files as source of truth. Generate a Glissade deck in <code>decks/talk.json</code> with speaker notes on every slide, then run <code>glissade check</code> and fix anything invalid."',
    response: 'Generated the deck, added speaker notes to each slide, ran validation, and corrected schema issues before finishing.'
  },
  cursor: {
    context: 'Example workflow for Cursor or VS Code agent mode',
    prompt: '"Read <code>AGENTS.md</code> plus <code>glissade.schema.json</code>. Create a short product demo deck with valid JSON only, then explain what changed so I can review it quickly."',
    response: 'Created a schema-valid deck, summarized the edits, and kept the output easy to inspect inside the editor diff.'
  }
};

function initAgentTabs() {
  const tabs = document.querySelectorAll('#agentTabs .agent-tab');
  const contextEl = document.getElementById('agentContextLine');
  const promptEl = document.getElementById('agentPromptQuote');
  const responseEl = document.getElementById('agentResponseText');

  if (!tabs.length || !contextEl || !promptEl || !responseEl) return;

  function renderAgent(key) {
    const data = AGENT_PROMPTS[key];
    if (!data) return;

    tabs.forEach(tab => {
      const isActive = tab.getAttribute('data-agent') === key;
      tab.classList.toggle('active', isActive);
      tab.setAttribute('aria-pressed', String(isActive));
    });

    contextEl.textContent = data.context;
    promptEl.innerHTML = data.prompt;
    responseEl.innerHTML = data.response;
  }

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      renderAgent(tab.getAttribute('data-agent'));
    });
  });

  renderAgent('claude');
}

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
      <div class="slide-eyebrow">RELEASE 0.14.0</div>
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
  "eyebrow": "Four views at once",
  "heading": "2x2 Matrix Analysis",
  "quads": [
    { "subheading": "Problem", "body": "<p>Summarise constraint in one short paragraph.</p>" },
    { "subheading": "Evidence", "body": "<p>Data and metrics supporting the claim.</p>" },
    { "subheading": "Options", "bullets": ["Option A: Pilot", "Option B: Rollout"] },
    { "subheading": "Recommendation", "body": "<p>Call to action or key decision.</p>" }
  ]
}`,
    html: `
      <div class="slide-eyebrow" style="font-size: 0.75rem;">Four views at once</div>
      <h3 style="font-size: 1.3rem; margin-bottom: 10px;">2x2 Matrix Analysis</h3>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
        <div class="grid-card" style="padding: 10px;"><strong>Problem</strong><p style="font-size: 0.8rem; margin-top: 4px;">Summarise constraint in one short paragraph.</p></div>
        <div class="grid-card" style="padding: 10px;"><strong>Evidence</strong><p style="font-size: 0.8rem; margin-top: 4px;">Data and metrics supporting the claim.</p></div>
        <div class="grid-card" style="padding: 10px;"><strong>Options</strong><ul style="font-size: 0.8rem; margin-top: 4px; padding-left: 14px;"><li>Option A: Pilot</li><li>Option B: Rollout</li></ul></div>
        <div class="grid-card" style="padding: 10px;"><strong>Recommendation</strong><p style="font-size: 0.8rem; margin-top: 4px;">Call to action or key decision.</p></div>
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
