"""Assemble deterministic MarketFlow AI inputs without calling an LLM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .competitor_analysis import build_competitor_analysis, load_product
    from .price_analysis import analyze_prices, load_competitors
    from .review_analysis import analyze_reviews, load_reviews
except ImportError:  # Supports: python analysis/output_schema.py ...
    from competitor_analysis import build_competitor_analysis, load_product
    from price_analysis import analyze_prices, load_competitors
    from review_analysis import analyze_reviews, load_reviews


OUTPUT_VERSION = "1.0.0"
REQUIRED_DATASET_FILES = ("product.json", "competitors.json", "reviews.csv")


def build_deterministic_output(dataset_dir: str | Path) -> dict[str, Any]:
    """Build the complete deterministic context bundle for one Demo product."""
    directory = Path(dataset_dir)
    _require_dataset_files(directory)

    product = load_product(directory / "product.json")
    competitors = load_competitors(directory / "competitors.json")
    reviews = load_reviews(directory / "reviews.csv")
    _validate_review_references(competitors, reviews)

    return {
        "analysis_version": OUTPUT_VERSION,
        "dataset": {
            "dataset_id": product["dataset_id"],
            "dataset_version": product["dataset_version"],
            "data_source_type": product["source_type"],
            "competitor_count": len(competitors),
            "review_count": len(reviews),
        },
        "product_input": {
            **product,
            "evidence_ids": [product["product_id"]],
            "confidence": 1,
            "conclusion_source_type": "data_fact",
        },
        "price_analysis": analyze_prices(competitors),
        "review_analysis": analyze_reviews(reviews),
        "competitor_analysis_base": build_competitor_analysis(
            product, competitors
        ),
    }


def analyze_all_demo_datasets(data_root: str | Path) -> dict[str, dict[str, Any]]:
    """Generate deterministic results for every valid Demo directory."""
    root = Path(data_root)
    results: dict[str, dict[str, Any]] = {}
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        if all((directory / filename).is_file() for filename in REQUIRED_DATASET_FILES):
            results[directory.name] = build_deterministic_output(directory)
    if not results:
        raise ValueError(f"No Demo datasets found under {root}")
    return results


def _require_dataset_files(directory: Path) -> None:
    if not directory.is_dir():
        raise ValueError(f"Dataset directory does not exist: {directory}")
    missing = [
        filename
        for filename in REQUIRED_DATASET_FILES
        if not (directory / filename).is_file()
    ]
    if missing:
        raise ValueError(f"Dataset {directory} is missing: {missing}")


def _validate_review_references(
    competitors: list[dict[str, Any]], reviews: list[dict[str, Any]]
) -> None:
    valid_ids = {item["competitor_id"] for item in competitors}
    invalid_refs = sorted(
        {
            item["competitor_id"]
            for item in reviews
            if item["competitor_id"] not in valid_ids
        }
    )
    if invalid_refs:
        raise ValueError(f"Reviews reference unknown competitors: {invalid_refs}")


def main() -> None:
    """Print deterministic JSON for manual inspection or pipeline input."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        type=Path,
        help="A Demo dataset directory, or data/ when --all is used.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Analyze every valid Demo directory under the supplied path.",
    )
    args = parser.parse_args()
    result = (
        analyze_all_demo_datasets(args.path)
        if args.all
        else build_deterministic_output(args.path)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

