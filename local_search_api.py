"""Local-only product search API backed by Ollama and the Supabase products table."""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from scraper.config import ConfigurationError, load_database_config


HOST = "127.0.0.1"
PORT = 8001
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5-coder:1.5b"
MAX_BODY_BYTES = 8_192


def interpret_query(query):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Turn a shopping search into useful product database search terms. "
                        'Return JSON only as {"terms":["term", ...]}. Include the key product '
                        "type and up to four specific synonyms or attributes. Do not answer the user."
                    ),
                },
                {"role": "user", "content": query},
            ],
            "options": {"temperature": 0},
        },
        timeout=90,
    )
    response.raise_for_status()
    message = response.json().get("message", {}).get("content", "")
    parsed = json.loads(message)
    terms = parsed.get("terms", [])
    if not isinstance(terms, list):
        raise ValueError("The local model returned an invalid search response.")

    safe_terms = []
    for term in terms:
        if not isinstance(term, str):
            continue
        term = re.sub(r"[^a-zA-Z0-9 -]", " ", term).strip()[:60]
        if term and term.casefold() not in {item.casefold() for item in safe_terms}:
            safe_terms.append(term)
        if len(safe_terms) == 5:
            break
    if not safe_terms:
        raise ValueError("The local model did not return any search terms.")
    return safe_terms


def search_products(query):
    terms = interpret_query(query)
    database = load_database_config()
    filters = []
    for term in terms:
        pattern = f"*{term}*"
        filters.extend(
            [
                f"title.ilike.{pattern}",
                f"description.ilike.{pattern}",
                f"category.ilike.{pattern}",
            ]
        )
    result = requests.get(
        f"{database.url}/rest/v1/products",
        headers={
            "apikey": database.secret_key,
            "Authorization": f"Bearer {database.secret_key}",
        },
        params={
            "select": "id,title,description,price,currency,product_url,source,category,scraped_at",
            "or": f"({','.join(filters)})",
            "order": "price.asc",
            "limit": "60",
        },
        timeout=20,
    )
    result.raise_for_status()
    products = result.json()

    def relevance(product):
        searchable = " ".join(
            str(product.get(field) or "") for field in ("title", "description", "category")
        ).casefold()
        return sum(1 for term in terms if term.casefold() in searchable)

    products.sort(key=lambda product: (-relevance(product), float(product["price"])))
    return products


class SearchHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        if self.path != "/api/search":
            self.send_json(404, {"error": "Not found."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                self.send_json(400, {"error": "Search query is empty or too long."})
                return
            payload = json.loads(self.rfile.read(length))
            query = payload.get("query", "") if isinstance(payload, dict) else ""
            if not isinstance(query, str) or not query.strip() or len(query) > 300:
                self.send_json(400, {"error": "Enter a search query under 300 characters."})
                return
            self.send_json(200, {"products": search_products(query.strip())})
        except ConfigurationError as error:
            self.send_json(503, {"error": str(error)})
        except requests.ConnectionError as error:
            if "11434" in str(error):
                message = "Ollama is not running locally. Start Ollama and try again."
            else:
                message = "Could not connect to Ollama or Supabase. Check that both are available."
            self.send_json(503, {"error": message})
        except requests.Timeout:
            self.send_json(504, {"error": "Search timed out. Try again in a moment."})
        except requests.HTTPError as error:
            response_url = error.response.url if error.response is not None else ""
            if "11434" in response_url:
                message = f"Ollama could not load {MODEL}. Run `ollama pull {MODEL}` and try again."
                status = 503
            elif error.response is not None and error.response.status_code >= 500:
                message = "The local model or Supabase returned an error. Check the local services."
                status = 502
            else:
                message = "Supabase rejected the search request. Check its table access and credentials."
                status = 502
            self.send_json(status, {"error": message})
        except (json.JSONDecodeError, ValueError):
            self.send_json(502, {"error": "The local model returned an invalid response. Try again."})
        except Exception:
            self.send_json(500, {"error": "Local search failed. Check the API terminal for details."})

    def log_message(self, format, *args):
        print(f"[local-search] {format % args}")


if __name__ == "__main__":
    try:
        load_database_config()
    except ConfigurationError as error:
        raise SystemExit(str(error)) from None
    print(f"Shoppie local search API listening at http://{HOST}:{PORT}")
    print(f"Using Ollama model: {MODEL}")
    ThreadingHTTPServer((HOST, PORT), SearchHandler).serve_forever()
