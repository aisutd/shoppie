"""Run with streamlit run dashboard.py; shared logic lives in backend/."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from backend.models import SearchRequest
from backend.service import ShoppingService
from db.embeddings import DIMENSIONS, MODEL_NAME, MODEL_REVISION
from scraper.evaluate import evaluate_fixtures, evaluate_captures
from backend.discovery import discover_report
from backend.access import permitted_page_retailers
from backend.settings import configuration_status
from backend.gemini import allow_calls

st.set_page_config(page_title="Shoppie · laptop finder", page_icon="🛍️", layout="wide")
st.title("Shoppie")
st.caption("Find the right configuration. Compare offers with evidence.")

with st.sidebar:
    st.header("Your search")
    mode_label = st.radio("Data source", ["Demo · synthetic fixtures", "Live · permitted sources"])
    mode = "demo" if mode_label.startswith("Demo") else "live"
    provider = None
    storage_source = "local"
    consent = st.checkbox("Allow Gemini API calls for this action", help="Explicit opt-in. Google generation and Search grounding may be billed. No calls happen just by opening this dashboard.")
    provided_urls = []
    if mode == "demo":
        st.info("Offline teaching data. Prices and retailer offers are synthetic.")
    else:
        provider = "gemini"
        st.caption("Automatic discovery: Gemini with Google Search grounding. Citation links remain unverified candidates until scraping and validation succeed.")
        storage_choice = st.selectbox("Offer storage", ["Local live collection", "Supabase · read only"])
        storage_source = "supabase" if storage_choice.startswith("Supabase") else "local"
        st.caption("Page access enabled for: " + (", ".join(sorted(permitted_page_retailers())) or "none — configure only retailer access your team is permitted to use"))
        with st.expander("Test permitted product URLs directly"):
            entered = st.text_area("Exact product URLs (one per line, maximum 8)")
            provided_urls = [value.strip() for value in entered.splitlines() if value.strip()]
            st.caption("These are provided URLs, not automatic discovery. Access checks still apply.")
    brand = st.selectbox("Brand", ["Any", "Apple", "Lenovo", "Dell", "HP", "Asus", "Acer"])
    category = st.selectbox("Category", ["laptop", "Any"])
    availability = st.selectbox("Availability", ["in_stock", "Any", "out_of_stock", "unknown"])
    use_price = st.checkbox("Apply a price range")
    minimum = st.number_input("Minimum USD", min_value=0, value=0, disabled=not use_price)
    maximum = st.number_input("Maximum USD", min_value=0, value=2500, disabled=not use_price)
    with st.expander("Exact configuration"):
        model_number = st.text_input("Model number (optional)")
        ram = st.selectbox("RAM (GB)", ["From query", 8, 16, 24, 32, 64])
        storage = st.selectbox("Storage (GB)", ["From query", 256, 512, 1000, 2000])
        cpu = st.text_input("CPU (optional)", help="Example: Apple M5, Intel Core i7-1360P")
        color = st.text_input("Color (optional)")
        screen = st.selectbox("Screen size (inches)", ["From query", 13.3, 13.6, 14.0, 15.3, 15.6, 16.0])
    browser = st.checkbox("Render JavaScript with Chromium", disabled=mode == "demo")
    headed = st.checkbox("Show browser while collecting", disabled=not browser or mode == "demo")
    ai_review = st.checkbox("Optional Gemini validation review", disabled=mode == "demo" or storage_source == "supabase", help="Can flag uncertain data for review; cannot override exact hardware conflicts.")
    use_gemini = st.checkbox("Optional Gemini evidence summary", help="Needs Gemini configuration and consent. Only verified live offers are sent; deterministic explanations always work.")
    if mode == "live":
        if st.button("Check Supabase (read only)"):
            try:
                from backend.supabase import SupabaseStore
                checker = SupabaseStore()
                st.session_state["supabase_status"] = {"inspection": checker.inspect(), "read": checker.refresh()}
            except ValueError as error:
                st.session_state["supabase_status"] = {"error": str(error), "writes": 0}
        if "supabase_status" in st.session_state:
            st.json(st.session_state["supabase_status"])



service_key = f"service_{mode}_{storage_source}"
result_key = f"result_{mode}_{storage_source}"
if service_key not in st.session_state or not isinstance(st.session_state[service_key], ShoppingService):
    try:
        st.session_state[service_key] = ShoppingService(mode=mode, storage=storage_source)
        st.session_state.pop(result_key, None)
    except ValueError as error:
        st.error(str(error))
        st.stop()
service = st.session_state[service_key]
query = st.text_input("Which laptop are you looking for?", value="Apple MacBook Air M5 16GB RAM 512GB SSD")
left, right = st.columns([1, 3])
find = left.button("Read shared products" if storage_source == "supabase" else "Find offers", type="primary", width="stretch")
indexed_only = right.button("Search indexed products")
discover_only = st.button("Discover candidate links only") if mode == "live" and storage_source == "local" else False
search_tab, monitor_tab, info_tab = st.tabs(["Search & compare", "Scraper monitoring", "Search & embeddings"])

if discover_only:
    try:
        with allow_calls(consent):
            st.session_state["live_discovery"] = discover_report(query, provider=provider)
    except ValueError as error:
        st.session_state["live_discovery"] = {"provider": provider, "error": str(error), "urls": []}

if find or indexed_only:
    try:
        request = SearchRequest(q=query, brand=None if brand == "Any" else brand,
            category=None if category == "Any" else category,
            availability=None if availability == "Any" else availability,
            min_price=minimum if use_price else None, max_price=maximum if use_price else None,
            model_number=model_number.strip() or None, cpu=cpu.strip() or None,
            color=color.strip() or None, screen_inches=screen if isinstance(screen, float) else None,
            ram_gb=ram if isinstance(ram, int) else None,
            storage_gb=storage if isinstance(storage, int) else None)
        with search_tab:
            if find:
                progress = st.progress(0.0, text="Finding candidates")
                def update(status):
                    total = max(status.get("discovered", 0), 1)
                    value = min(status.get("processed", 0) / total, 1.0)
                    progress.progress(value, text=f"{status['stage'].capitalize()} · {status.get('accepted',0)} accepted")
                if len(provided_urls) > 8:
                    raise ValueError("Provide at most eight product URLs")
                if storage_source == "supabase":
                    service.refresh_shared()
                else:
                    with allow_calls(consent):
                        service.collect(query, browser=browser, headed=headed, progress=update,
                                        provider=provider, urls=provided_urls or None, request=request, ai_review=ai_review)
                progress.progress(1.0, text=service.status["stage"].capitalize())
            with st.spinner("Searching indexed products and comparing exact configurations…"):
                with allow_calls(consent):
                    result = service.deals(request, use_gemini)
            st.session_state[result_key] = result
    except Exception as error:
        st.session_state.pop(result_key, None)
        st.error(str(error) if isinstance(error, ValueError) else "Local collection or model initialization failed. Check SETUP_MACOS.md and the terminal.")

with search_tab:
    if mode == "live" and storage_source == "local" and "live_discovery" in st.session_state:
        discovery = st.session_state["live_discovery"]
        st.subheader("Candidate links · no offers verified yet")
        if discovery.get("error"):
            st.error(discovery["error"])
        st.dataframe([{"Candidate URL": url} for url in discovery.get("urls", [])], width="stretch")
        if discovery.get("search_suggestions_html"):
            with st.expander("Google Search attribution", expanded=True):
                # Google's attribution snippet runs in an isolated frame with scripts disabled
                csp = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src https://www.gstatic.com https://www.google.com; base-uri 'none'; form-action 'none'"
                st.components.v1.html('<meta http-equiv="Content-Security-Policy" content="' + csp + '">' + discovery["search_suggestions_html"], height=180, scrolling=True)
        with st.expander("Discovery details"):
            st.json(discovery)
    result = st.session_state.get(result_key)
    if result:
        if mode == "demo":
            st.warning("Synthetic demonstration · freshness evaluated at fixture time: October 28, 2026, 12:00 UTC. These are not live offers.")
        if mode == "live":
            st.info("Only observations with collection evidence can be recommended. Automatic validation does not independently verify checkout prices. Source evidence and observation times are shown below.")
            if service.status["stage"] in {"failed", "no_matches"}:
                st.warning("The latest collection did not produce matching offers. Any results below are previously stored observations, not successes from this run.")
        a, b, c = st.columns(3)
        a.metric("Exact comparable offers", len(result["offers"]))
        b.metric("Retailers represented", result["retailers"])
        c.metric("Search time", f"{result['search_seconds']:.3f}s")
        st.write(result["explanation"])
        if not result["offers"]:
            st.info("No exact, fresh, available offers to compare. Review incomplete candidates below or collect accessible pages.")
        for offer in result["offers"]:
            with st.container(border=True):
                name, price = st.columns([4, 1])
                name.subheader(offer["title"])
                name.caption(f"{offer['retailer_key']} · {offer['match_status']} · {offer['availability']}")
                st.caption(f"Source: {offer.get('verification_status', 'unverified')} · Observed: {offer['scraped_at']}")
                price.metric("Known total USD" if offer["total_price"] else "Subtotal USD", offer["total_price"] or offer["price"])
                attrs = offer["attributes"]
                st.write(f"RAM: {attrs.get('ram_gb', 'unknown')} GB · Storage: {attrs.get('storage_gb', 'unknown')} GB · CPU: {attrs.get('cpu', 'unknown')}")
                for reason in offer["deal_reasons"]:
                    st.write("• " + reason)
                if offer["recommended"]:
                    st.success("Recommended among offers with known totals")
                if mode == "live":
                    st.link_button("Open retailer page", offer["source_url"])
                else:
                    st.caption("Synthetic fixture URL (not a verified retailer offer)")
                    st.code(offer["source_url"], language=None)
        with st.expander("All relevant candidates and review reasons", expanded=not bool(result["offers"])):
            excluded = {item["id"]: item["reason"] for item in result["excluded"]}
            st.dataframe([{"Product": row["title"], "Retailer": row["retailer_key"],
                "USD": row["price"], "RAM": row["attributes"].get("ram_gb"),
                "Storage": row["attributes"].get("storage_gb"), "CPU": row["attributes"].get("cpu"),
                "Availability": row["availability"], "Match": row["match_status"],
                "Shipping USD": row.get("shipping_cost"), "URL": row["source_url"],
                "Condition": row.get("condition") or "unknown", "Deal eligibility": excluded.get(row["id"], "eligible"),
                "Source evidence": row.get("verification_status", "unverified"), "Observed": row["scraped_at"],
                "Cosine": round(row["semantic_score"], 4), "Reason": "; ".join(row["reasons"])}
                for row in result["results"]], width="stretch")
    else:
        if mode == "demo":
            st.info("Try the sample search to compare the two exact 16GB / 512GB demo offers. Conflicting variants are excluded; missing specifications require review.")
        else:
            st.info("Discover candidate links or collect permitted pages. No live offer has been verified in this session.")

with monitor_tab:
    st.subheader("Latest collection")
    status = service.status
    st.write(f"Stage: {status['stage']} · Mode: {mode}")
    columns = st.columns(4)
    for column, label, key in zip(columns, ["Discovered URLs", "Pages attempted", "Accepted", "Rejected"], ["discovered", "attempted", "accepted", "rejected"]):
        column.metric(label, status.get(key, 0))
    columns = st.columns(4)
    for column, label, key in zip(columns, ["Fetched pages", "Extracted records", "Invalid records", "Failed scrapes"], ["fetched", "extracted", "invalid_records", "failed_scrapes"]):
        column.metric(label, status.get(key, 0))
    st.caption("Accepted = source records passing validation, including unavailable or incompatible products. Exact matches, skips, and storage outcomes are separate.")
    st.dataframe([{key: status.get(key, 0) for key in ("processed", "skipped", "duplicate_urls", "invalid_urls", "compatible", "incompatible", "manual_review", "unavailable", "unknown_availability", "saved", "unchanged", "storage_failures", "blocked_pages", "ai_reviews", "ai_review_required")}], width="stretch")
    if status.get("acceptance_rate") is not None:
        st.write(f"Validation pass rate per attempted page: {status['acceptance_rate']:.1%}")
    st.caption("Live incorrect-data accuracy is not measured without human-labeled checks. Missing fields and validation success do not establish accuracy.")
    if status.get("events"):
        st.dataframe(status["events"], width="stretch")
    for error in status.get("errors", []):
        st.error(error)
    with st.expander("Collection details"):
        st.json(status)
    st.subheader("Labeled scraper evaluation")
    st.caption("Synthetic fixtures include a deliberate incorrect price, missing data, and a blocked page. These rates do not measure live retailer reliability.")
    quality_source = st.selectbox("Evaluation data", ["Synthetic labeled fixtures", "Archived real Target captures · October 14"])
    if st.button("Run fixture reliability evaluation"):
        st.session_state["quality_report"] = evaluate_captures() if quality_source.startswith("Archived") else evaluate_fixtures()
    if "quality_report" in st.session_state:
        report = st.session_state["quality_report"]
        st.write(report["source"])
        st.dataframe([{"Metric": key, "Value": value} for key, value in report["metrics"].items()], width="stretch")
        st.write("Missing values are counted separately from wrong present values. Accuracy denominators:", report["denominators"])
        st.json({key: report[key] for key in ("counts", "quality_counts", "missing_fields", "incorrect_fields", "failures_by_retailer_and_type")})
        st.dataframe(report["pages"], width="stretch")
        st.download_button("Download quality report", __import__('json').dumps(report, indent=2), "scraper-quality.json", "application/json")

with info_tab:
    st.write("Model:", MODEL_NAME)
    st.write("Pinned revision:", MODEL_REVISION)
    st.write("Dimensions:", DIMENSIONS)
    loaded = storage_source == "local" or service.store.rows is not None
    count = len(service.products()) if loaded and service.store.listings() else 0
    st.write("Products visible in this mode:", count if loaded else "Shared source not read yet")
    st.write("Storage:", "Supabase read only; new vectors cached locally" if storage_source == "supabase" else "Local SQLite")
    st.write("AI and connection configuration:", configuration_status())
    st.caption("SBERT uses the cached 384-dimensional MiniLM model. Hosted connectivity is checked only on an explicit read action. Existing public.products rows without source/stock evidence require review.")
    st.write("Data source:", "Synthetic fixtures" if mode == "demo" else "Live observations")
    st.caption("Product vectors are reused by input hash and model/template version. Search relevance and deal comparison are separate steps. The dashboard and API share backend functions.")
