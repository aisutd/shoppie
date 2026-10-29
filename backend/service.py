"""Business functions shared by Streamlit, FastAPI, and the command line."""

from datetime import datetime
from pathlib import Path

from backend.coordinator import collect
from backend.deals import rank_deals
from backend.explanations import explain
from backend.search import search
from backend.storage import LocalStore, ROOT
from db.embeddings import index_store

DEMO_TIME = datetime.fromisoformat("2026-10-28T12:00:00+00:00")


class ShoppingService:
    def __init__(self, store=None, mode="demo", model=None, storage="local"):
        if mode not in {"demo", "live"}:
            raise ValueError("mode must be demo or live")
        self.mode = mode
        if storage not in {"local", "supabase"} or (storage == "supabase" and mode != "live"):
            raise ValueError("Supabase is a read-only Live source; Demo uses local fixtures")
        self.storage = storage
        if store is None and storage == "supabase":
            from backend.supabase import SupabaseStore
            store = SupabaseStore()
        self.store = store or LocalStore(ROOT / f".local/{mode}.sqlite3")
        self.model = model
        self.status = {"stage": "idle", "source": mode, "discovered": 0, "attempted": 0,
                       "accepted": 0, "errors": []}

    def collect(self, query, browser=False, headed=False, progress=None, provider=None, urls=None, request=None, ai_review=False):
        if self.storage == "supabase":
            raise ValueError("Supabase is read-only. Select local Live storage to collect offers; shared uploads require separate mentor approval.")
        def update(status):
            self.status = status
            if progress:
                progress(status)
        self.status = collect(self.store, query, self.mode, browser, headed, update,
                              provider=provider, urls=urls, request=request, ai_review=ai_review)
        if self.status["stage"] != "collected":
            return self.status
        self.status["stage"] = "embedding"
        if progress:
            progress(self.status)
        try:
            self.status["embeddings"] = index_store(self.store, self.model)
        except Exception:
            self.status["stage"] = "failed"
            self.status["errors"].append("Embedding initialization failed; check the local model cache and dependencies.")
            if progress:
                progress(self.status)
            raise
        self.status["stage"] = "ready"
        if progress:
            progress(self.status)
        return self.status

    def refresh_shared(self):
        if self.storage != "supabase":
            raise ValueError("Select the read-only Supabase source first")
        report = self.store.refresh()
        self.status = {"stage": "embedding", "source": "live", "discovered": 0,
                       "attempted": 0, "accepted": report["accepted"], "errors": report["errors"]}
        self.status["embeddings"] = index_store(self.store, self.model)
        self.status["stage"] = "ready"
        return report

    def ensure_demo(self):
        if self.mode == "demo" and not self.store.listings():
            self.collect("demo fixtures")

    def search(self, request):
        self.ensure_demo()
        if self.storage == "supabase" and self.store.rows is None:
            self.refresh_shared()
        elif self.storage == "supabase" and not self.status.get("embeddings"):
            self.status["embeddings"] = index_store(self.store, self.model)
        response = search(self.store, request, self.model, source=self.mode)
        response["source"] = "synthetic fixtures" if self.mode == "demo" else "live observations"
        response["collection_run_id"] = self.status.get("run_id")
        response["latest_collection_stage"] = self.status["stage"]
        response["explanation"] = "Relevance ranking uses exact compatibility, identifiers, then an equal-weight cosine/keyword score. This score is not a probability. Missing identity facts require review."
        return response

    def deals(self, request, use_gemini=False):
        response = self.search(request.model_copy(update={"limit": 50}))
        deals = rank_deals(response["results"], self.store, now=DEMO_TIME if self.mode == "demo" else None,
                           require_verified=self.mode == "live")
        deals["offers"] = deals["offers"][:request.limit]
        response.update(deals)
        response["comparison_as_of"] = DEMO_TIME.isoformat() if self.mode == "demo" else datetime.now().astimezone().isoformat()
        response["explanation"] = explain(deals, use_gemini)
        current = [row for row in deals["offers"] if row.get("source_verified")
                   and row.get("collection_run_id") == self.status.get("run_id")]
        response["live_two_retailer_milestone"] = (self.mode == "live" and self.status["stage"] == "ready"
            and len({row["retailer_key"] for row in current}) >= 2)
        return response

    def products(self):
        self.ensure_demo()
        from backend.provenance import source_evidence
        products = []
        for row in self.store.listings():
            evidence = source_evidence(row)
            if self.mode == "live" and evidence["data_source"] == "synthetic":
                continue
            if self.mode == "demo" and evidence["data_source"] != "synthetic":
                continue
            public = {key: value for key, value in row.items() if key not in {"raw_payload", "source_url_hash"}}
            products.append({**public, **evidence})
        return products
