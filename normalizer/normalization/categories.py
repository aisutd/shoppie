def normalize_label(value: str) -> str:
    return " ".join(value.casefold().split())


CATEGORY_ALIASES = {
    "laptop": "laptop",
    "laptops": "laptop",
    "notebook computers": "laptop",
    "monitor": "monitor",
    "monitors": "monitor",
    "computer monitors": "monitor",
    "headphones": "headphones",
    "headphone": "headphones",
    "keyboard": "keyboard",
    "keyboards": "keyboard",
}


def normalize_category(value: str | None) -> str:
    if not value or not value.strip():
        return "generic"

    label = normalize_label(value)
    return CATEGORY_ALIASES.get(label, label)