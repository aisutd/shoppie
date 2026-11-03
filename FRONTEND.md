# Shoppie frontend

The React frontend lives at the repository root and runs independently from the
Python scraper. It uses Vite and Tailwind CSS 3.

## Start the development server

Install Node.js, then run these commands from the repository root:

```powershell
npm install
npm run dev
```

Open the local URL printed by Vite. To create and preview a production build:

```powershell
npm run build
npm run preview
```

## Tailwind setup

- `tailwind.config.js` scans `index.html` and files in `src/`.
- `postcss.config.js` connects Tailwind to Vite's CSS processing.
- `src/index.css` loads Tailwind's base, component, and utility layers.
- `tailwind.config.js` defines the `animate-fade-in` and `animate-fade-up`
  utilities used by the starter page.

The current page is a minimal navy blue front page with the title “Shoppie”.
