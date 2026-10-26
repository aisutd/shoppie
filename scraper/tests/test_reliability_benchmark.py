"""Benchmark tests use fake subprocesses, never live retailers."""
import json
import subprocess
from types import SimpleNamespace
import pytest
from scraper.tests import run_reliability_benchmark as benchmark
from scraper.tests import build_reliability_cases as builder

URL = 'https://www.bestbuy.com/product/synthetic-laptop/TEST123'


def accepted_output(title='Synthetic laptop'):
    record = dict(retailer='bestbuy', product_id='TEST123', product_url=URL,
                  title=title, price='123.45', currency='USD', availability=None,
                  seller=None, discount=None, observed_at='2026-10-26T12:00:00+00:00', extraction_method='html')
    return json.dumps(record, indent=2) + '\nACCEPTED\nResults: fetched=1, extracted=1, validated=1, rejected=0, saved=0, failed_saves=0\n'


def test_fallback_preserves_both_attempts(monkeypatch):
    failure_output = 'HTTP failure\nDIAGNOSTIC: {"failure_stage":"fetch","failure_category":"request_timeout","fallback_allowed":true}'
    processes = iter([SimpleNamespace(stdout=failure_output, stderr='http stderr', returncode=1),
                      SimpleNamespace(stdout=accepted_output(), stderr='', returncode=0)])
    monkeypatch.setattr(benchmark.subprocess, 'run', lambda *a, **kw: next(processes))
    attempts = benchmark.run_scraper(URL)
    assert [a['mode'] for a in attempts] == ['http', 'browser']
    assert attempts[0]['stdout'] == failure_output
    assert attempts[0]['stderr'] == 'http stderr'
    assert attempts[0]['return_code'] == 1
    assert attempts[1]['produced_valid_record']


def test_timeout_preserves_partial_bytes(monkeypatch):
    def timeout(*a, **kw):
        raise subprocess.TimeoutExpired(a[0], 90, output=b'partial stdout', stderr=b'partial stderr')
    monkeypatch.setattr(benchmark.subprocess, 'run', timeout)
    attempt = benchmark.run_attempt(URL, 'http')
    assert attempt['timed_out'] and attempt['return_code'] is None
    assert attempt['stdout'] == 'partial stdout'
    assert attempt['stderr'] == 'partial stderr'
    assert not attempt['produced_valid_record']


def test_success_skips_browser(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=accepted_output(), stderr='', returncode=0)
    monkeypatch.setattr(benchmark.subprocess, 'run', run)
    assert len(benchmark.run_scraper(URL)) == 1
    assert calls[0][0] == benchmark.sys.executable


def test_builder_preserves_reviewed_cases_and_removed_urls():
    original = [dict(url=URL, expected=dict(should_accept=False, price="123.45"),
                     notes="reviewed note", needs_review=False, custom="keep")]
    result = builder.build_cases([URL, URL + "?seller=2", URL], original)
    assert result[0] == original[0]
    assert original == result[:1]
    assert len(result) == 2
    assert result[1]["expected"]["should_accept"] is None
    assert builder.build_cases([], original) == original


def test_benchmark_never_writes_cases_and_preserves_review(monkeypatch, tmp_path):
    cases = tmp_path / "cases.json"
    results = tmp_path / "results.json"
    source = dict(url=URL, expected=dict(should_accept=False, title='Laptop "Pro"'),
                  notes="keep me", needs_review=False, review_status="reviewed")
    cases.write_text(json.dumps([source]), encoding="utf-8")
    before = cases.read_bytes()
    monkeypatch.setattr(benchmark, "CASES_FILE", cases)
    monkeypatch.setattr(benchmark, "OUTPUT_FILE", results)
    monkeypatch.setattr(benchmark, "read_urls", lambda: [URL])
    monkeypatch.setattr(benchmark.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout=accepted_output(), stderr="", returncode=0))
    benchmark.main()
    assert cases.read_bytes() == before
    saved = json.loads(results.read_text(encoding="utf-8"))[0]
    for key in ("expected", "notes", "needs_review", "review_status"):
        assert saved[key] == source[key]


@pytest.mark.parametrize("urls,key", [
    (["https://www.amazon.com/dp/B0GR6KJ72L", "https://www.amazon.com/name/dp/B0GR6KJ72L?sr=8-3",
      "https://www.amazon.com/gp/product/B0GR6KJ72L"], "amazon:B0GR6KJ72L"),
    (["https://www.bestbuy.com/product/laptop/J3PPHF7KP6", "https://www.bestbuy.com/product/other-slug/J3PPHF7KP6"],
     "bestbuy:J3PPHF7KP6"),
    (["https://www.bestbuy.com/site/laptop/6571026.p", "https://www.bestbuy.com/site/other/6571026.p?skuId=6571026"],
     "bestbuy:6571026"),
    (["https://www.target.com/p/laptop/-/A-95288385?preselect=91122087",
      "https://www.target.com/p/laptop/-/A-91122087"], "target:91122087"),
    (["https://www.walmart.com/ip/laptop/18156070263", "https://www.walmart.com/ip/18156070263?seller=other"],
     "walmart:18156070263"),
])
def test_grouping_uses_supported_product_identity(urls, key):
    assert {benchmark.get_product_key(url) for url in urls} == {key}


def test_target_preselected_variants_remain_different():
    base = "https://www.target.com/p/laptop/-/A-95288385"
    assert len({benchmark.get_product_key(url) for url in [base, base + "?preselect=91122087",
                                                        base + "?preselect=91122088"]}) == 3
    assert benchmark.get_product_key(base + "?preselect=bad") is None
    assert benchmark.get_product_key("https://www.bestbuy.com.evil.test/product/laptop/J3PPHF7KP6") is None


def test_json_decoding_preserves_quotes_unicode_and_braces(monkeypatch):
    title = 'Synthetic laptop "Pro" \\ special\t— {new}: café!'
    output = 'Page 1/1\nnoise\n' + accepted_output(title)
    monkeypatch.setattr(benchmark.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout=output, stderr="", returncode=0))
    attempt = benchmark.run_attempt(URL, "http")
    assert attempt["produced_valid_record"]
    assert attempt["record"]["title"] == title


@pytest.mark.parametrize("change,return_code", [
    (lambda s: s.replace("validated=1", "validated=10"), 0),
    (lambda s: s.replace("rejected=0", "rejected=1"), 0),
    (lambda s: s.replace("ACCEPTED", "not ACCEPTED"), 0),
    (lambda s: s.replace('"title": "Synthetic laptop",', ''), 0),
    (lambda s: s.replace('"price": "123.45"', '"price": "NaN"'), 0),
    (lambda s: s, 1),
    (lambda s: s + s, 0),
    (lambda s: s.replace("TEST123", "OTHER123"), 0),
])
def test_inconsistent_output_is_never_accepted(monkeypatch, change, return_code):
    monkeypatch.setattr(benchmark.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout=change(accepted_output()), stderr="", returncode=return_code))
    assert not benchmark.run_attempt(URL, "http")["produced_valid_record"]


def test_diagnostic_stage_is_saved(monkeypatch):
    diagnostic = dict(failure_stage="validation", failure_category="validation_failed",
                      failure_detail="Required fields failed validation.")
    output = 'DIAGNOSTIC: ' + json.dumps(diagnostic) + '\nResults: fetched=1, extracted=1, validated=0, rejected=1, saved=0, failed_saves=0\n'
    monkeypatch.setattr(benchmark.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout=output, stderr="", returncode=1))
    attempt = benchmark.run_attempt(URL, "http")
    assert attempt["fetch_status"] == "succeeded"
    assert attempt["extraction_status"] == "succeeded"
    assert attempt["validation_status"] == "failed"
    assert attempt["failure_category"] == "validation_failed"


def test_metrics_do_not_score_unreviewed_expectations():
    row = dict(retailer="bestbuy", scraper_result="accepted", attempts=[], duplicate_of=None,
               failure_category=None, needs_review=True, expected=dict(should_accept=False, price="999.00"),
               observed=dict(title="Synthetic laptop", price="123.45", currency="USD", availability=None))
    assert "reviewed_ground_truth" not in benchmark.summarize([row])
    row["needs_review"] = False
    scored = benchmark.summarize([row])["reviewed_ground_truth"]
    assert scored["false_accepts"] == 1
    assert scored["accepted_with_incorrect_reviewed_fields"] == 1
    assert scored["fields"]["price"]["accuracy"] == 0


def test_reviewed_false_reject_and_decimal_comparison():
    row = dict(retailer="bestbuy", scraper_result="rejected", attempts=[], duplicate_of=None,
               failure_category=None, needs_review=False, expected=dict(should_accept=True, price=123.45),
               observed=dict(title="Synthetic laptop", price="123.450", currency="USD", availability=None))
    assert benchmark.summarize([row])["reviewed_ground_truth"]["false_rejects"] == 1
    row["scraper_result"] = "accepted"
    assert benchmark.summarize([row])["reviewed_ground_truth"]["fields"]["price"]["accuracy"] == 1


def test_same_identity_different_offer_url_is_not_accepted(monkeypatch):
    monkeypatch.setattr(benchmark.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout=accepted_output().replace(URL, URL + "?seller=other"), stderr="", returncode=0))
    assert not benchmark.run_attempt(URL, "http")["produced_valid_record"]


def test_real_cli_json_contract_offline():
    fixture = benchmark.ROOT / "scraper/tests/fixtures/synthetic_product.html"
    process = subprocess.run([benchmark.sys.executable, "-X", "utf8", "-m", "scraper.main", "--url", URL,
                              "--html", str(fixture)], cwd=benchmark.ROOT, capture_output=True,
                             text=True, encoding="utf-8", timeout=15)
    records, counters, diagnostics = benchmark.parse_output(process.stdout)
    assert process.returncode == 0, process.stderr
    assert len(records) == 1 and records[0]["price"] == "123.45"
    assert counters["validated"] == 1
    assert diagnostics == []


def test_benchmark_obeys_terminal_production_fallback_decision(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout='DIAGNOSTIC: {"failure_stage":"fetch","failure_category":"challenge_or_access_denied","fallback_allowed":false}',
                               stderr="", returncode=1)
    monkeypatch.setattr(benchmark.subprocess, "run", run)
    attempts = benchmark.run_scraper(URL)
    assert len(attempts) == len(calls) == 1
    assert '--http-only' in calls[0] and '--browser' not in calls[0]


def test_benchmark_preserves_confirmed_browser_navigation_event(monkeypatch):
    event = dict(mode="browser", navigation=dict(final_url=URL, navigation_retries=1))
    monkeypatch.setattr(benchmark.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout='ATTEMPT: ' + json.dumps(event) + '\n' + accepted_output(), stderr="", returncode=0))
    attempt = benchmark.run_attempt(URL, "browser")
    assert attempt['produced_valid_record'] and attempt['stage_events'] == [event]
