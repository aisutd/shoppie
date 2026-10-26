"""Measure the real CLI; never save products or overwrite reviewed cases."""
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scraper.scraper import clean_url, identify_product

INPUT_FILE = Path(__file__).with_name('reliability_urls.txt')
CASES_FILE = Path(__file__).with_name('reliability_cases.json')
OUTPUT_FILE = Path(__file__).with_name('reliability_results.json')
FIELDS = ('title', 'price', 'currency', 'availability', 'product_id')


def get_product_key(url):
    try:
        retailer, product_id = identify_product(url)
        return f'{retailer}:{product_id}'
    except ValueError:
        return None


def get_retailer(url):
    key = get_product_key(url)
    return key.split(':', 1)[0] if key else 'unknown'


def output_text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''


def parse_output(output):
    """Decode standalone JSON blocks; never regex-capture JSON string values."""
    records, diagnostics, counters = [], [], None
    lines = output.splitlines()
    for index, line in enumerate(lines):
        if line.startswith('DIAGNOSTIC: '):
            try:
                value = json.loads(line.removeprefix('DIAGNOSTIC: '))
                if isinstance(value, dict):
                    diagnostics.append(value)
            except ValueError:
                pass
        if line == '{':
            for end in range(index + 1, len(lines)):
                if lines[end] == '}':
                    try:
                        value = json.loads('\n'.join(lines[index:end + 1]))
                        if isinstance(value, dict) and set(FIELDS).issubset(value):
                            records.append(value)
                    except ValueError:
                        pass
                    break
        if line.startswith('Results: '):
            pairs = line.removeprefix('Results: ').split(', ')
            if all(re.fullmatch(r'[a-z_]+=\d+', pair) for pair in pairs):
                parsed = dict(pair.split('=') for pair in pairs)
                required = {'fetched', 'extracted', 'validated', 'rejected', 'saved', 'failed_saves'}
                if set(parsed) == required and len(pairs) == len(required):
                    counters = {key: int(value) for key, value in parsed.items()}
    return records, counters, diagnostics


def run_attempt(url, mode):
    command = [sys.executable, '-X', 'utf8', '-u', '-m', 'scraper.main', '--url', url]
    if mode == 'browser':
        command.append('--browser')
    else:
        command.append('--http-only')
    command.append('--keep-html')
    attempt = dict(mode=mode, command=command, return_code=None, timed_out=False,
                   stdout='', stderr='', produced_valid_record=False, record=None,
                   fetch_status='unknown', extraction_status='unknown', validation_status='unknown',
                   failure_stage=None, failure_category=None, failure_detail=None, fallback_allowed=False)
    try:
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=90)
        attempt.update(return_code=process.returncode, stdout=process.stdout or '', stderr=process.stderr or '')
    except subprocess.TimeoutExpired as error:
        attempt.update(timed_out=True, stdout=output_text(error.stdout), stderr=output_text(error.stderr),
                       failure_category='process_timeout', failure_detail='Benchmark process exceeded 90 seconds.',
                       fallback_allowed=get_product_key(url) is not None)
    except OSError:
        attempt.update(failure_stage='before_fetch', failure_category='process_start_error',
                       failure_detail='Could not start scraper interpreter.')
    records, counters, diagnostics = parse_output(attempt['stdout'])
    attempt['stage_events'] = []
    for line in attempt['stdout'].splitlines():
        if line.startswith('ATTEMPT: '):
            try:
                event = json.loads(line.removeprefix('ATTEMPT: '))
                if isinstance(event, dict):
                    attempt['stage_events'].append(event)
            except ValueError:
                pass
    attempt['counters'], attempt['diagnostics'] = counters, diagnostics
    accepted = (not attempt['timed_out'] and attempt['return_code'] == 0
                and counters == dict(fetched=1, extracted=1, validated=1, rejected=0, saved=0, failed_saves=0)
                and len(records) == 1 and 'ACCEPTED' in attempt['stdout'].splitlines())
    if accepted:
        from scraper.validator import validate_record
        try:
            product = validate_record(records[0])
            accepted = (identify_product(url) == (product.retailer, product.product_id)
                        and clean_url(url) == product.product_url)
        except ValueError:
            accepted = False
    attempt['produced_valid_record'] = accepted
    attempt['record'] = records[0] if len(records) == 1 else None
    if counters:
        for status, counter in (('fetch', 'fetched'), ('extraction', 'extracted'), ('validation', 'validated')):
            attempt[status + '_status'] = 'succeeded' if counters[counter] == 1 else 'not_reached'
    if diagnostics:
        attempt['fallback_allowed'] = diagnostics[-1].get('fallback_allowed', False)
        for key in ('failure_stage', 'failure_category', 'failure_detail'):
            attempt[key] = diagnostics[-1].get(key)
        stage = attempt['failure_stage']
        if stage in ('fetch', 'extraction', 'validation'):
            attempt[stage + '_status'] = 'failed'
            if stage == 'extraction':
                # Browser extraction may reject a received snapshot inside readiness.
                attempt['fetch_status'] = 'succeeded'
    if not accepted and not attempt['failure_category']:
        attempt.update(failure_category='unclassified_failure',
                       failure_detail='CLI did not produce one consistent validated record; inspect captured output.')
    return attempt


def run_scraper(url):
    attempts = [run_attempt(url, 'http')]
    if not attempts[0]['produced_valid_record'] and attempts[0]['fallback_allowed']:
        attempts.append(run_attempt(url, 'browser'))
    return attempts


def read_urls(path=INPUT_FILE):
    return list(dict.fromkeys(line.strip() for line in path.read_text(encoding='utf-8-sig').splitlines()
                             if line.strip() and not line.lstrip().startswith('#')))


def summarize(results):
    attempts = [attempt for result in results for attempt in result['attempts']]
    retailers = {}
    for retailer in sorted({result['retailer'] for result in results}):
        rows = [result for result in results if result['retailer'] == retailer]
        retailers[retailer] = dict(urls=len(rows), accepted=sum(r['scraper_result'] == 'accepted' for r in rows),
                                  rejected=sum(r['scraper_result'] == 'rejected' for r in rows))
    summary = dict(urls=len(results), per_retailer=retailers,
                   failure_categories=dict(Counter(a['failure_category'] for a in attempts if a['failure_category'])),
                   final_failure_categories=dict(Counter(r['failure_category'] for r in results if r['failure_category'])),
                   same_product_variants=sum(r['duplicate_of'] is not None for r in results),
                   browser_fallback_attempts=sum(a['mode'] == 'browser' for a in attempts),
                   browser_fallback_recoveries=sum(a['mode'] == 'browser' and a['produced_valid_record'] for a in attempts),
                   timeout_count=sum(a['timed_out'] or a['failure_category'] in {
                       'request_timeout', 'browser_navigation_timeout', 'readiness_timeout'} for a in attempts),
                   connection_reset_count=sum(a['failure_category'] == 'connection_reset' for a in attempts),
                   redirect_failure_count=sum(a['failure_category'] in {'redirect_identity_mismatch', 'redirect_limit'} for a in attempts),
                   challenge_count=sum(a['failure_category'] == 'challenge_or_access_denied' for a in attempts))
    summary['per_mode'] = {}
    for mode in ('http', 'browser'):
        rows = [a for a in attempts if a['mode'] == mode]
        summary['per_mode'][mode] = dict(attempts=len(rows),
            accepted=sum(a['produced_valid_record'] for a in rows),
            **{stage + '_successes': sum(a[stage + '_status'] == 'succeeded' for a in rows)
               for stage in ('fetch', 'extraction', 'validation')})
    # Review flags are explicit; unknown expectations are never scored as wrong.
    reviewed = [r for r in results if r.get('needs_review') is False or r.get('review_status') == 'reviewed']
    scoring = dict(reviewed_cases=len(reviewed), acceptance_comparisons=0, false_accepts=0,
                   false_rejects=0, accepted_with_incorrect_reviewed_fields=0, fields={})
    for row in reviewed:
        expected = row['expected']
        should_accept = expected.get('should_accept', row.get('should_accept'))
        accepted = row['scraper_result'] == 'accepted'
        if isinstance(should_accept, bool):
            scoring['acceptance_comparisons'] += 1
            scoring['false_accepts'] += accepted and not should_accept
            scoring['false_rejects'] += not accepted and should_accept
        bad_fields = False
        for field in ('title', 'price', 'currency', 'availability'):
            if not accepted or field not in expected or (expected[field] is None and field not in row.get('reviewed_fields', [])):
                continue
            actual, truth = row['observed'][field], expected[field]
            equal = actual == truth
            if field == 'price':
                try:
                    equal = Decimal(str(actual)) == Decimal(str(truth))
                except InvalidOperation:
                    equal = False
            values = scoring['fields'].setdefault(field, dict(compared=0, correct=0))
            values['compared'] += 1
            values['correct'] += equal
            bad_fields |= not equal
        scoring['accepted_with_incorrect_reviewed_fields'] += bad_fields
    if scoring['acceptance_comparisons'] or scoring['fields']:
        for values in scoring['fields'].values():
            values['accuracy'] = values['correct'] / values['compared']
        summary['reviewed_ground_truth'] = scoring
    return summary


def main():
    reviewed = {case['url']: case for case in json.loads(CASES_FILE.read_text(encoding='utf-8'))} if CASES_FILE.exists() else {}
    results, seen = [], {}
    started_at = datetime.now(timezone.utc).isoformat()
    for index, url in enumerate(read_urls(), 1):
        print(f'[{index}] {url}', flush=True)
        attempts = run_scraper(url)
        final = attempts[-1]
        key = get_product_key(url)
        source = reviewed.get(url, {})
        result = dict(url=url, retailer=get_retailer(url), product_key=key, benchmark_started_at=started_at,
                      duplicate_of=seen.get(key) if key else None,
                      attempts=attempts, scraper_result='accepted' if final['produced_valid_record'] else 'rejected',
                      observed={field: (final['record'] or {}).get(field) for field in FIELDS},
                      expected=source.get('expected', {}), notes=source.get('notes', ''),
                      needs_review=source.get('needs_review', True), review_status=source.get('review_status'),
                      should_accept=source.get('should_accept'), reviewed_fields=source.get('reviewed_fields', []),
                      reviewed_case=source,
                      browser_attempt_status=('completed' if len(attempts) > 1 else
                          'not_run_http_accepted' if final['produced_valid_record'] else 'not_run_terminal_http_failure'))
        for name in ('fetch_status', 'extraction_status', 'validation_status', 'failure_stage', 'failure_category', 'failure_detail'):
            result[name] = final[name]
        if key:
            seen.setdefault(key, url)
        results.append(result)
        OUTPUT_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
        print(f"  {result['scraper_result']}: {result['failure_category']}", flush=True)
    print(f'Saved {len(results)} URL observations to {OUTPUT_FILE}')
    summary = summarize(results)
    OUTPUT_FILE.with_name('reliability_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
