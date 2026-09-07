"""Prompt package builder for the strategy recommendation stage.

This module accepts deterministic analysis plus previously validated insight
objects. It does not connect to, configure, or invoke an LLM.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
PROMPT_PATH = MODULE_DIR / "prompts" / "strategy_prompt.md"
RECOMMENDATION_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "recommendation.schema.json"
)
INSUFFICIENT_EVIDENCE = "insufficient_evidence"


def build_strategy_advisor_package(
    analysis_output: dict[str, Any],
    product_analysis: dict[str, Any],
    competitor_analysis: dict[str, Any],
    pain_points: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a strategy prompt package without performing model inference."""
    _require_mapping(analysis_output, "analysis_output")
    for key in ("dataset", "product_input", "price_analysis", "review_analysis"):
        _required_mapping(analysis_output, key)
    _require_mapping(product_analysis, "product_analysis")
    _require_mapping(competitor_analysis, "competitor_analysis")
    if not isinstance(pain_points, list) or any(
        not isinstance(item, dict) for item in pain_points
    ):
        raise ValueError("pain_points must be a list of validated objects")

    allowed_evidence_ids = _collect_analysis_evidence_ids(analysis_output)
    recommendation_schema = _read_json(RECOMMENDATION_SCHEMA_PATH)
    output_contract = {
        "type": "array",
        "items": recommendation_schema,
    }

    return {
        "stage": "strategy_advisor",
        "system_prompt": _read_text(PROMPT_PATH),
        "input_data": {
            "deterministic_analysis": {
                "dataset": analysis_output["dataset"],
                "product_input": analysis_output["product_input"],
                "price_analysis": analysis_output["price_analysis"],
                "review_analysis": analysis_output["review_analysis"],
            },
            "validated_product_analysis": product_analysis,
            "validated_competitor_analysis": competitor_analysis,
            "validated_pain_points": pain_points,
            "allowed_evidence_ids": allowed_evidence_ids,
        },
        "output_schema": output_contract,
        "output_schema_path": str(RECOMMENDATION_SCHEMA_PATH),
        "insufficient_evidence_signal": INSUFFICIENT_EVIDENCE,
    }


def _collect_analysis_evidence_ids(
    analysis_output: dict[str, Any],
) -> list[str]:
    identifiers: set[str] = set()
    product = analysis_output.get("product_input", {})
    product_id = product.get("product_id") if isinstance(product, dict) else None
    if isinstance(product_id, str) and product_id:
        identifiers.add(product_id)

    competitor_base = analysis_output.get("competitor_analysis_base", {})
    if isinstance(competitor_base, dict):
        for row in competitor_base.get("competitor_matrix", []):
            if isinstance(row, dict):
                competitor_id = row.get("competitor_id")
                if isinstance(competitor_id, str) and competitor_id:
                    identifiers.add(competitor_id)

    review_analysis = analysis_output.get("review_analysis", {})
    if isinstance(review_analysis, dict):
        for record in review_analysis.get("evidence_records", []):
            if isinstance(record, dict):
                review_id = record.get("review_id")
                if isinstance(review_id, str) and review_id:
                    identifiers.add(review_id)
    if not identifiers:
        raise ValueError("analysis_output contains no valid evidence IDs")
    return sorted(identifiers)


def _required_mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    _require_mapping(item, key)
    return item


def _require_mapping(value: Any, name: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)

