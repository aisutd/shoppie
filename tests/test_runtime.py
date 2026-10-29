"""Opt-in checks using the real cached SBERT model and installed Chromium."""

import math
import json
import os
from pathlib import Path
import pytest

pytestmark = pytest.mark.skipif(os.environ.get("SHOPPIE_RUNTIME_TESTS") != "1", reason="set SHOPPIE_RUNTIME_TESTS=1 after local model/browser setup")


def test_real_sbert_and_labeled_search(tmp_path):
    from db.embeddings import load_model, generate_batch, generate_embedding
    from backend.service import ShoppingService
    from backend.storage import LocalStore
    from backend.evaluation import evaluate_search
    model = load_model(local_files_only=True)
    vectors = generate_batch(model, ["Apple laptop", "Lenovo laptop"])
    query = generate_embedding(model, "Apple laptop")
    assert len(query) == 384 and all(math.isfinite(x) for x in query)
    assert math.isclose(sum(x*x for x in query), 1, abs_tol=1e-6)
    assert sum(a*b for a,b in zip(query,vectors[0])) > sum(a*b for a,b in zip(query,vectors[1]))
    service = ShoppingService(LocalStore(tmp_path/"real.sqlite3"), model=model)
    service.collect("synthetic fixtures")
    report = evaluate_search(service)
    assert report["macro_precision_at_k"] == 1.0


def test_chromium_renders_controlled_page_and_stops_challenge():
    from playwright.sync_api import sync_playwright
    from scraper.scraper import read_browser_page, extract_product
    from scraper.evaluate import FIXTURE_DIR
    root = Path(__file__).resolve().parents[1]
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(root/".local/browsers"))
    url = "https://www.bestbuy.com/product/synthetic-macbook-air/SYNTH001"
    with sync_playwright() as p:
        with p.chromium.launch(headless=True) as browser:
            page = browser.new_page()
            fixture = (FIXTURE_DIR/"01_bestbuy.html").read_text()
            encoded = json.dumps(fixture).replace("</", "<\\/")
            dynamic = '<html><body>Loading<script>setTimeout(() => { document.body.innerHTML = ' + encoded + '; }, 150);</script></body></html>'
            page.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=dynamic))
            html = read_browser_page(page, url)
            assert extract_product(html, url)["attributes"]["ram_gb"] == 16
            page.unroute("**/*")
            page.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body="<h1>Verify you are human</h1>"))
            with pytest.raises(ValueError, match="bot check"):
                read_browser_page(page, url)
            page.unroute("**/*")
            redirected = '<script>history.replaceState(null, "", "/not-requested-product");</script><h1>Untrusted product</h1>'
            page.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=redirected))
            with pytest.raises(ValueError, match="redirected"):
                read_browser_page(page, url)


def test_streamlit_app_launch_and_demo_search():
    from streamlit.testing.v1 import AppTest
    root = Path(__file__).resolve().parents[1]
    app = AppTest.from_file(str(root/"dashboard.py"), default_timeout=60).run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    assert any(metric.label == "Exact comparable offers" and metric.value == "2" for metric in app.metric)
