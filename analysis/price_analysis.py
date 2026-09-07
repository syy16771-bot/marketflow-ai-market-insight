"""Deterministic competitor price calculations for MarketFlow AI."""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


_MONEY_STEP = Decimal("0.01")
_REQUIRED_FIELDS = {
    "competitor_id",
    "name",
    "price",
    "currency",
    "rating",
    "review_count",
    "features",
    "selling_points",
}


def load_competitors(path: str | Path) -> list[dict[str, Any]]:
    """Load and minimally validate a competitors.json file."""
    source_path = Path(path)
    with source_path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list) or not records:
        raise ValueError(f"{source_path} must contain a non-empty JSON array")

    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Competitor at index {index} must be an object")

        missing = _REQUIRED_FIELDS.difference(record)
        if missing:
            raise ValueError(
                f"Competitor at index {index} is missing: {sorted(missing)}"
            )

        competitor_id = record["competitor_id"]
        if not isinstance(competitor_id, str) or not competitor_id.strip():
            raise ValueError(f"Competitor at index {index} has an invalid ID")
        if competitor_id in seen_ids:
            raise ValueError(f"Duplicate competitor_id: {competitor_id}")
        seen_ids.add(competitor_id)

        _as_non_negative_decimal(record["price"], f"{competitor_id}.price")
        rating = _as_non_negative_decimal(
            record["rating"], f"{competitor_id}.rating"
        )
        if rating > 5:
            raise ValueError(f"{competitor_id}.rating cannot exceed 5")

        for field_name in ("features", "selling_points"):
            values = record[field_name]
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError(
                    f"{competitor_id}.{field_name} must be an array of non-empty strings"
                )

        if isinstance(record["review_count"], bool) or not isinstance(
            record["review_count"], int
        ):
            raise ValueError(f"{competitor_id}.review_count must be an integer")
        if record["review_count"] < 0:
            raise ValueError(f"{competitor_id}.review_count cannot be negative")

    return records


def analyze_prices(competitors: list[dict[str, Any]]) -> dict[str, Any]:
    """Return stable price statistics, including the PRD-required average."""
    if not competitors:
        raise ValueError("At least one competitor is required for price analysis")

    currencies = {str(item["currency"]).strip().upper() for item in competitors}
    if len(currencies) != 1:
        raise ValueError("All competitors must use the same currency")
    currency = currencies.pop()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError(f"Invalid ISO-style currency code: {currency}")

    priced_records = [
        (
            item["competitor_id"],
            _as_non_negative_decimal(item["price"], f"{item['competitor_id']}.price"),
        )
        for item in competitors
    ]
    prices = sorted(price for _, price in priced_records)
    total = sum(prices, Decimal("0"))
    average = (total / Decimal(len(prices))).quantize(
        _MONEY_STEP, rounding=ROUND_HALF_UP
    )
    median = _median(prices).quantize(_MONEY_STEP, rounding=ROUND_HALF_UP)

    return {
        "currency": currency,
        "minimum": _money(prices[0]),
        "maximum": _money(prices[-1]),
        "average": _money(average),
        "median": _money(median),
        "sample_size": len(prices),
        "evidence_ids": [competitor_id for competitor_id, _ in priced_records],
        "confidence": 1,
        "source_type": "calculated",
    }


def to_schema_price_range(price_analysis: dict[str, Any]) -> dict[str, Any]:
    """Project full statistics into the locked competitor-analysis Schema.

    The current Schema has no average field. The full deterministic bundle keeps
    average, while this projection intentionally exposes only allowed fields.
    """
    allowed_fields = (
        "currency",
        "minimum",
        "median",
        "maximum",
        "sample_size",
        "evidence_ids",
        "confidence",
        "source_type",
    )
    return {field: price_analysis[field] for field in allowed_fields}


def _as_non_negative_decimal(value: Any, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = Decimal(str(value))
    except Exception as error:
        raise ValueError(f"{field_name} must be numeric") from error
    if not number.is_finite() or number < 0:
        raise ValueError(f"{field_name} must be a finite non-negative number")
    return number


def _median(sorted_values: list[Decimal]) -> Decimal:
    midpoint = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[midpoint]
    return (sorted_values[midpoint - 1] + sorted_values[midpoint]) / Decimal("2")


def _money(value: Decimal) -> float:
    return float(value.quantize(_MONEY_STEP, rounding=ROUND_HALF_UP))
