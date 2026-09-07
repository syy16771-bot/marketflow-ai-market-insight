"""Prompt package builder for competitor and customer insight generation.

No LLM client is implemented here. Numeric and factual inputs are selected from
the deterministic analysis bundle and marked immutable for a future caller.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
PROMPT_PATH = MODULE_DIR / "prompts" / "customer_insight_prompt.md"
COMPETITOR_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "competitor_analysis.schema.json"
)
PAIN_POINT_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "pain_point.schema.json"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"


def build_customer_insight_package(
    analysis_output: dict[str, Any],
) -> dict[str, Any]:
    """Build the customer-insight prompt package from deterministic output."""
    _require_mapping(analysis_output, "analysis_output")
    required_sections = (
        "dataset",
        "product_input",
        "price_analysis",
        "review_analysis",
        "competitor_analysis_base",
    )
    sections = {
        key: _required_mapping(analysis_output, key) for key in required_sections
    }

    allowed_evidence_ids = _collect_evidence_ids(sections)
    output_contract = {
        "type": "object",
        "additionalProperties": False,
        "required": ["competitor_analysis", "pain_points"],
        "properties": {
            "competitor_analysis": _read_json(COMPETITOR_SCHEMA_PATH),
            "pain_points": {
                "type": "array",
                "items": _read_json(PAIN_POINT_SCHEMA_PATH),
            },
        },
    }

    return {
        "stage": "customer_insight",
        "system_prompt": _read_text(PROMPT_PATH),
        "input_data": {
            **sections,
            "allowed_evidence_ids": allowed_evidence_ids,
            "immutable_paths": [
                "price_analysis",
                "competitor_analysis_base.price_range",
                "competitor_analysis_base.competitor_matrix",
                "review_analysis.review_statistics",
                "review_analysis.competitor_review_counts",
                "review_analysis.pain_point_signals[*].count",
                "review_analysis.pain_point_signals[*].frequency_level",
                "review_analysis.pain_point_signals[*].sample_size",
            ],
        },
        "output_schema": output_contract,
        "output_schema_paths": [
            str(COMPETITOR_SCHEMA_PATH),
            str(PAIN_POINT_SCHEMA_PATH),
        ],
        "insufficient_evidence_signal": INSUFFICIENT_EVIDENCE,
    }


def _collect_evidence_ids(sections: dict[str, dict[str, Any]]) -> list[str]:
    identifiers: set[str] = set()
    product_id = sections["product_input"].get("product_id")
    if isinstance(product_id, str) and product_id:
        identifiers.add(product_id)

    matrix = sections["competitor_analysis_base"].get("competitor_matrix", [])
    if isinstance(matrix, list):
        for row in matrix:
            if isinstance(row, dict):
                competitor_id = row.get("competitor_id")
                if isinstance(competitor_id, str) and competitor_id:
                    identifiers.add(competitor_id)

    records = sections["review_analysis"].get("evidence_records", [])
    if isinstance(records, list):
        for record in records:
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
        raise ValueError(f"{name} must be an object from the analysis layer")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)

