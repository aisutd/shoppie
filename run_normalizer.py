from pathlib import Path

from normalizer.pipeline import normalize_files


ROOT = Path(__file__).resolve().parent


def main() -> None:
    output_path = ROOT / "data" / "output" / "products.json"

    result = normalize_files(
        inputs={
            "target": ROOT / "data/input/target.json",
            "walmart": ROOT / "data/input/walmart.json",
            "bestbuy": ROOT / "data/input/bestbuy.json",
            "amazon": ROOT / "data/input/amazon.json",
        },
        output_path=output_path,
    )

    print(f"Created {len(result.products)} canonical product(s).")
    print(f"Recorded {len(result.issues)} processing issue(s).")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()