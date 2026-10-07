from normalizer.normalization.categories import normalize_label


COMMON_FIELD_ALIASES = {
    "color": "color",
    "colour": "color",
    "connectivity": "connectivity",
}


CATEGORY_FIELD_ALIASES = {
    "laptop": {
        "ram": "ram_gb",
        "ram_gb": "ram_gb",
        "installed memory": "ram_gb",
        "storage": "storage_gb",
        "storage capacity": "storage_gb",
        "storage_gb": "storage_gb",
        "processor": "cpu",
        "cpu": "cpu",
        "screen size": "screen_inches",
        "screen_inches": "screen_inches",
    },
    "monitor": {
        "screen size": "screen_inches",
        "screen_inches": "screen_inches",
        "refresh rate": "refresh_rate_hz",
        "refresh_rate_hz": "refresh_rate_hz",
        "resolution": "resolution",
        "panel type": "panel_type",
    },
    "headphones": {
        "wireless": "wireless",
        "noise cancelling": "noise_cancelling",
        "noise canceling": "noise_cancelling",
    },
    "keyboard": {
        "wireless": "wireless",
        "switch type": "switch_type",
        "layout": "layout",
    },
}


def normalize_field(category: str, raw_name: str) -> str | None:
    label = normalize_label(raw_name)
    category_aliases = CATEGORY_FIELD_ALIASES.get(category, {})

    return category_aliases.get(
        label,
        COMMON_FIELD_ALIASES.get(label),
    )