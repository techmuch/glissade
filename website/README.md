# Glissade Website

This directory contains the source code for the official landing page and web showcase for **Glissade**.

## Structure

```
website/
├── index.html   # Main HTML page with semantic markup & Open Graph tags
├── styles.css   # Modern dark-mode & glassmorphism styling, CSS design tokens
├── app.js       # Interactive phone-remote simulator & layout preview code
└── README.md    # Documentation
```

## Previewing Locally

Because the website uses pure HTML5, CSS3, and modern JavaScript without heavy node bundlers, you can serve it with any local static HTTP server:

### Option 1: Python HTTP Server
```bash
python3 -m http.server 8080 -d website
```
Then open `http://localhost:8080` in your browser.

### Option 2: Node static server / npx
```bash
npx serve website
```

## Deploying

### GitHub Pages (Recommended)
You can deploy this site directly via GitHub Pages:
1. Go to repository **Settings** -> **Pages**.
2. Select **Source**: `GitHub Actions` or `Deploy from a branch`.
3. If using `Deploy from a branch`, choose branch `main` and folder `/website`.

### Cloudflare Pages / Vercel
- **Build command**: (Leave empty)
- **Output directory**: `website`
