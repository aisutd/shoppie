"""Precision@K on explicit synthetic labels, without calling it live accuracy."""

import json
from backend.models import SearchRequest
from scraper.evaluate import FIXTURE_DIR


def evaluate_search(service):
    labels = json.loads((FIXTURE_DIR / "search_labels.json").read_text())
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())
    urls = {item["id"]: item["url"] for item in manifest["pages"]}
    scores = []
    for item in labels["queries"]:
        expected = {urls[identity] for identity in item["relevant_fixtures"]}
        response = service.search(SearchRequest(q=item["q"], limit=item["k"]))
        found = {row["source_url"] for row in response["results"]}
        hits = len(found & expected)
        scores.append({"query": item["q"], "k": item["k"], "retrieved": len(found),
                       "precision_at_k": hits/item["k"], "recall": hits/len(expected)})
    return {"source": labels["source"], "queries": scores,
            "macro_precision_at_k": sum(row["precision_at_k"] for row in scores)/len(scores)}
