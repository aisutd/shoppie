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

## Local AI product search

Product search uses Ollama locally and queries `public.products` in Supabase.
Keep `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in `scraper/.env`; the key is
read only by the local Python API and is never sent to the browser.

1. Install Ollama, then download the model with `ollama pull qwen2.5-coder:1.5b`.
2. Install the Python dependencies with `python -m pip install -r requirements.txt`.
3. Start the API from the repository root with `python local_search_api.py`.
4. In another terminal, start the frontend with `npm run dev`.

Ollama must be running on its default local address (`127.0.0.1:11434`). The
search API binds only to `127.0.0.1:8001` and the Vite development server
forwards `/api` requests to it.

## Tailwind setup

- `tailwind.config.js` scans `index.html` and files in `src/`.
- `postcss.config.js` connects Tailwind to Vite's CSS processing.
- `src/index.css` loads Tailwind's base, component, and utility layers.
- `tailwind.config.js` defines the `animate-fade-in` and `animate-fade-up`
  utilities used by the starter page.

The current page is a minimal navy blue front page with the title “Shoppie”.
