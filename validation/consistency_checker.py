"""Cross-layer consistency checks and final-report validation gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .evidence_validator import validate_evidence
    from .schema_validator import validate_json_schema
except ImportError:  # Supports direct loading from the validation directory.
    from evidence_validator import validate_evidence
    from schema_validator import validate_json_schema


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"


def check_consistency(
    analysis_output: dict[str, Any],
    competitor_analysis: dict[str, Any],
    pain_points: list[dict[str, Any]],
    report_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare generated outputs with immutable deterministic values."""
    errors: list[str] = []
    warnings: list[str] = []

    expected_competitor = analysis_output.get("competitor_analysis_base", {})
    expected_price_range = expected_competitor.get("price_range")
    actual_price_range = competitor_analysis.get("price_range")
    if actual_price_range != expected_price_range:
        errors.append(
            "competitor_analysis.price_range does not exactly match "
            "analysis.competitor_analysis_base.price_range"
        )

    expected_matrix = expected_competitor.get("competitor_matrix", [])
    actual_matrix = competitor_analysis.get("competitor_matrix", [])
    if actual_matrix != expected_matrix:
        errors.append(
            "competitor_analysis.competitor_matrix was modified or does not "
            "cover the deterministic competitor matrix"
        )

    expected_product_id = expected_competitor.get("product_id")
    if competitor_analysis.get("product_id") != expected_product_id:
        errors.append(
            "competitor_analysis.product_id does not match the analysis result"
        )

    expected_competitor_ids = {
        row.get("competitor_id") for row in expected_matrix if isinstance(row, dict)
    }
    actual_competitor_ids = {
        row.get("competitor_id") for row in actual_matrix if isinstance(row, dict)
    }
    nonexistent_competitors = sorted(
        item
        for item in actual_competitor_ids.difference(expected_competitor_ids)
        if item is not None
    )
    if nonexistent_competitors:
        errors.append(
            f"competitor_analysis contains unknown competitors "
            f"{nonexistent_competitors}"
        )

    review_analysis = analysis_output.get("review_analysis", {})
    review_statistics = review_analysis.get("review_statistics", {})
    expected_review_count = review_statistics.get("total_reviews")
    signals = review_analysis.get("pain_point_signals", [])

    for position, pain_point in enumerate(pain_points):
        path = f"pain_points[{position}]"
        frequency = pain_point.get("frequency", {})
        if frequency.get("sample_size") != expected_review_count:
            errors.append(
                f"{path}.frequency.sample_size does not match analysis review count"
            )

        evidence_ids = frequency.get("evidence_ids", [])
        matching_signals = [
            signal
            for signal in signals
            if isinstance(signal, dict)
            and set(signal.get("evidence_ids", [])) == set(evidence_ids)
        ]
        if len(matching_signals) != 1:
            errors.append(
                f"{path}.frequency does not map to exactly one analysis pain signal"
            )
        else:
            signal = matching_signals[0]
            comparisons = {
                "count": signal.get("count"),
                "level": signal.get("frequency_level"),
                "sample_size": signal.get("sample_size"),
                "evidence_ids": signal.get("evidence_ids"),
                "confidence": signal.get("confidence"),
                "source_type": signal.get("source_type"),
            }
            if frequency != comparisons:
                errors.append(
                    f"{path}.frequency was recalculated or modified from analysis"
                )

        unknown_pain_competitors = sorted(
            item
            for item in pain_point.get("competitor_ids", [])
            if item not in expected_competitor_ids
        )
        if unknown_pain_competitors:
            errors.append(
                f"{path} contains unknown competitors {unknown_pain_competitors}"
            )

    if report_metadata is not None:
        dataset = report_metadata.get("dataset", {})
        if dataset.get("review_count") != expected_review_count:
            errors.append(
                "report dataset.review_count does not match analysis review count"
            )
        expected_dataset = analysis_output.get("dataset", {})
        for key in (
            "dataset_id",
            "dataset_version",
            "data_source_type",
            "competitor_count",
        ):
            if dataset.get(key) != expected_dataset.get(key):
                errors.append(f"report dataset.{key} does not match analysis")

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def validate_for_final_report(
    analysis_output: dict[str, Any],
    product_analysis: dict[str, Any],
    competitor_analysis: dict[str, Any],
    pain_points: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    report_metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return validation_summary only when every validation layer passes.

    A None summary is the explicit instruction not to generate final_report.
    """
    errors: list[str] = []
    warnings: list[str] = []

    schema_targets = [
        (
            "product_analysis",
            product_analysis,
            SCHEMAS_DIR / "product_analysis.schema.json",
        ),
        (
            "competitor_analysis",
            competitor_analysis,
            SCHEMAS_DIR / "competitor_analysis.schema.json",
        ),
    ]
    schema_targets.extend(
        (
            f"pain_points[{position}]",
            item,
            SCHEMAS_DIR / "pain_point.schema.json",
        )
        for position, item in enumerate(pain_points)
    )
    schema_targets.extend(
        (
            f"recommendations[{position}]",
            item,
            SCHEMAS_DIR / "recommendation.schema.json",
        )
        for position, item in enumerate(recommendations)
    )

    for label, instance, schema_path in schema_targets:
        result = validate_json_schema(instance, schema_path)
        errors.extend(f"schema:{label}: {error}" for error in result["errors"])

    evidence_result = validate_evidence(
        analysis_output,
        product_analysis,
        competitor_analysis,
        pain_points,
        recommendations,
    )
    errors.extend(f"evidence: {error}" for error in evidence_result["errors"])
    warnings.extend(evidence_result["warnings"])

    consistency_result = check_consistency(
        analysis_output,
        competitor_analysis,
        pain_points,
        report_metadata,
    )
    errors.extend(
        f"consistency: {error}" for error in consistency_result["errors"]
    )
    warnings.extend(consistency_result["warnings"])

    if errors:
        return None, errors

    validation_summary = {
        "schema_valid": True,
        "evidence_ids_valid": True,
        "calculations_verified": True,
        "unsupported_claim_count": evidence_result[
            "unsupported_claim_count"
        ],
        "warnings": sorted(set(warnings)),
    }
    return validation_summary, []

