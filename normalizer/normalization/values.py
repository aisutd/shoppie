import math
import re
from decimal import Decimal
from typing import Any


def parse_measurement(
    value: object,
    units: dict[str, Decimal],
) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("Expected a measurement, received a boolean.")

    if isinstance(value, (int, float)):
        # Numeric inputs are assumed to use the canonical unit.
        number = Decimal(str(value))
    elif isinstance(value, str):
        match = re.fullmatch(
            r"\s*(\d+(?:\.\d+)?)\s*([A-Za-z\"]+)\s*",
            value,
        )

        if not match:
            raise ValueError(f"Unsupported measurement: {value!r}")

        number_text, unit = match.groups()
        multiplier = units.get(unit.casefold())

        if multiplier is None:
            raise ValueError(f"Unsupported unit: {unit!r}")

        number = Decimal(number_text) * multiplier
    else:
        raise ValueError(f"Unsupported measurement type: {type(value).__name__}")

    if not number.is_finite() or number <= 0:
        raise ValueError("Measurement must be finite and positive.")

    return number


def parse_capacity_gb(value: object) -> int | float:
    number = parse_measurement(
        value,
        units={
            "gb": Decimal("1"),
            "tb": Decimal("1000"),
        },
    )

    return int(number) if number == number.to_integral_value() else float(number)


def parse_boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        label = value.strip().casefold()

        if label in {"yes", "true"}:
            return True

        if label in {"no", "false"}:
            return False

    raise ValueError(f"Unsupported boolean: {value!r}")


def normalize_value(field_name: str, value: Any) -> Any:
    if field_name in {"ram_gb", "storage_gb"}:
        return parse_capacity_gb(value)

    if field_name == "screen_inches":
        return float(
            parse_measurement(
                value,
                {
                    "in": Decimal("1"),
                    "inch": Decimal("1"),
                    "inches": Decimal("1"),
                    '"': Decimal("1"),
                },
            )
        )

    if field_name == "refresh_rate_hz":
        return float(
            parse_measurement(
                value,
                {"hz": Decimal("1")},
            )
        )

    if field_name in {"wireless", "noise_cancelling"}:
        return parse_boolean(value)

    if isinstance(value, str):
        return " ".join(value.split())

    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Value must be finite.")

    return value