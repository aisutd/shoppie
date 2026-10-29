"""Manual smoke command; importing this file never fetches retailer pages."""


def main():
    from scraper.main import main as scrape
    return scrape()


if __name__ == '__main__':
    raise SystemExit(main())
