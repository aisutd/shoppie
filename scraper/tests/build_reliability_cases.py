"""Add missing URL cases without replacing human-reviewed expectations."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scraper.tests.run_reliability_benchmark import get_retailer, read_urls

INPUT_FILE = Path(__file__).with_name('reliability_urls.txt')
OUTPUT_FILE = Path(__file__).with_name('reliability_cases.json')


def build_cases(urls, existing):
    # Retain even cases no longer in the URL list, and every existing field.
    cases = list(existing)
    known = {case['url'] for case in cases}
    for url in urls:
        if url in known:
            continue
        cases.append(dict(url=url, retailer=get_retailer(url),
                          expected=dict(should_accept=None, title=None, price=None,
                                        currency=None, availability=None),
                          needs_review=True, notes=''))
        known.add(url)
    return cases


def main():
    existing = json.loads(OUTPUT_FILE.read_text(encoding='utf-8')) if OUTPUT_FILE.exists() else []
    cases = build_cases(read_urls(INPUT_FILE), existing)
    if cases != existing:
        OUTPUT_FILE.write_text(json.dumps(cases, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print(f'{len(cases)} cases; added {len(cases) - len(existing)}. Existing reviews preserved.')


if __name__ == '__main__':
    main()
