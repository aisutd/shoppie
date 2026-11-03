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

Product search fuzzy-matches a five-minute local cache of `public.products` in
Supabase, so normal searches do not wait for model inference. Ollama is used as
a slower fallback when no catalog matches are found. Price phrases such as
`under $1,000`, `at most 500`, `over $200`, and `between $100 and $300` filter
the catalog by its stored product price.
When a query names a category present in the catalog, results are restricted
to matching categories so description keywords do not surface unrelated items.
Memory requests such as `at least 16 GB RAM` are checked against memory values
associated with `memory` or `RAM` in each product's title or description; a
matching number elsewhere in the name or a storage capacity does not satisfy it.
Queries using `cheap`, `affordable`, or similar terms return the lowest-priced
30% of the products that match the query and any explicit filters.
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
