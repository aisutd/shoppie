import json
from pathlib import Path

from normalizer.models import NormalizationResult


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_result(
    result: NormalizationResult,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )