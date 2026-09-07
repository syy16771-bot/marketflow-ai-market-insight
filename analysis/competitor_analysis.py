"""Build the deterministic part of competitor_analysis.schema.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .price_analysis import analyze_prices, load_competitors, to_schema_price_range
except ImportError:  # Supports direct execution from the analysis directory.
    from price_analysis import analyze_prices, load_competitors, to_schema_price_range


_PRODUCT_REQUIRED_FIELDS = {
    "dataset_id",
    "dataset_version",
    "source_type",
    "product_id",
    "product_name",
    "category",
    "target_market",
    "currency",
    "description",
}


def load_product(path: str | Path) -> dict[str, Any]:
    """Load and validate the fields required by the deterministic layer."""
    source_path = Path(path)
    with source_path.open("r", encoding="utf-8") as file:
        product = json.load(file)
    if not isinstance(product, dict):
        raise ValueError(f"{source_path} must contain a JSON object")
    missing = _PRODUCT_REQUIRED_FIELDS.difference(product)
    if missing:
        raise ValueError(f"{source_path} is missing fields: {sorted(missing)}")
    return product


def build_competitor_analysis(
    product: dict[str, Any], competitors: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return a Schema-compatible base for later Agent enrichment."""
    price_analysis = analyze_prices(competitors)
    if product["currency"].upper() != price_analysis["currency"]:
        raise ValueError("Product and competitors must use the same currency")

    matrix = []
    for competitor in competitors:
        matrix.append(
            {
                "competitor_id": competitor["competitor_id"],
                "name": competitor["name"],
                "price": competitor["price"],
                "currency": competitor["currency"].upper(),
                "rating": competitor["rating"],
                "review_count": competitor["review_count"],
                "features": competitor["features"],
                "selling_points": competitor["selling_points"],
                "evidence_ids": [competitor["competitor_id"]],
                "confidence": 1,
                "source_type": "data_fact",
            }
        )

    return {
        "product_id": product["product_id"],
        "price_range": to_schema_price_range(price_analysis),
        "competitor_matrix": matrix,
        "strengths": [],
        "weaknesses": [],
        "differentiation_opportunities": [],
    }


def analyze_competitor_dataset(dataset_dir: str | Path) -> dict[str, Any]:
    """Load one Demo directory and build its deterministic competitor output."""
    directory = Path(dataset_dir)
    product = load_product(directory / "product.json")
    competitors = load_competitors(directory / "competitors.json")
    return build_competitor_analysis(product, competitors)

