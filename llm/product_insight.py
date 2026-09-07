"""Prompt package builder for the product-insight LLM stage.

This module performs no model or network calls. It only selects trusted input
from the deterministic analysis bundle and attaches the existing output Schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
PROMPT_PATH = MODULE_DIR / "prompts" / "product_insight_prompt.md"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "product_analysis.schema.json"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"


def build_product_insight_package(
    analysis_output: dict[str, Any],
) -> dict[str, Any]:
    """Build an API-neutral prompt package from analysis-layer output only."""
    _require_mapping(analysis_output, "analysis_output")
    dataset = _required_mapping(analysis_output, "dataset")
    product_input = _required_mapping(analysis_output, "product_input")

    product_id = _required_text(product_input, "product_id")
    input_data = {
        "analysis_version": analysis_output.get("analysis_version"),
        "dataset": dataset,
        "product_input": product_input,
        "allowed_evidence_ids": [product_id],
    }

    return {
        "stage": "product_insight",
        "system_prompt": _read_text(PROMPT_PATH),
        "input_data": input_data,
        "output_schema": _read_json(SCHEMA_PATH),
        "output_schema_path": str(SCHEMA_PATH),
        "insufficient_evidence_signal": INSUFFICIENT_EVIDENCE,
    }


def _required_mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    _require_mapping(item, key)
    return item


def _require_mapping(value: Any, name: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object from the analysis layer")


def _required_text(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return item


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)

