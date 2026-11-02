"""Prompt for one product URL and run the existing validated upload pipeline."""

from scraper.main import main


def run():
    print("Shoppie product uploader")
    print("Paste an Amazon, Best Buy, Target, or Walmart laptop URL.")
    url = input("Product URL: ").strip()
    if not url:
        print("No URL entered. Nothing was uploaded.")
        input("Press Enter to close this window.")
        return 1

    print("\nFetching, validating, and uploading the product...\n")
    result = main(["--url", url, "--save"])
    input("\nPress Enter to close this window.")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled. No further action taken.")
        raise SystemExit(1)
