"""Evidence integrity checks for MarketFlow AI insight outputs."""

from __future__ import annotations

from typing import Any, Iterator


def validate_evidence(
    analysis_output: dict[str, Any],
    product_analysis: dict[str, Any],
    competitor_analysis: dict[str, Any],
    pain_points: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate evidence existence and relationships across all outputs."""
    index = _build_evidence_index(analysis_output)
    errors: list[str] = []
    warnings: list[str] = []
    unsupported_claim_count = 0

    output_sections = {
        "product_analysis": product_analysis,
        "competitor_analysis": competitor_analysis,
        "pain_points": pain_points,
        "recommendations": recommendations,
    }
    for path, claim in _walk_claims(output_sections):
        evidence_ids = claim.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            errors.append(f"{path}: conclusion has no evidence_ids")
            unsupported_claim_count += 1
            continue
        unknown = sorted(
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in index["all_ids"]
        )
        if unknown:
            errors.append(f"{path}: unknown evidence_ids {unknown}")
            unsupported_claim_count += 1

    valid_competitor_ids = index["competitor_ids"]
    valid_review_ids = index["review_ids"]
    review_to_competitor = index["review_to_competitor"]
    pain_point_map: dict[str, dict[str, Any]] = {}

    for position, pain_point in enumerate(pain_points):
        path = f"pain_points[{position}]"
        pain_point_id = pain_point.get("pain_point_id")
        if isinstance(pain_point_id, str) and pain_point_id:
            if pain_point_id in pain_point_map:
                errors.append(f"{path}: duplicate pain_point_id {pain_point_id!r}")
            pain_point_map[pain_point_id] = pain_point

        evidence_ids = pain_point.get("evidence_ids", [])
        invalid_review_ids = sorted(
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in valid_review_ids
        )
        if invalid_review_ids:
            errors.append(
                f"{path}: pain point evidence must reference reviews; invalid "
                f"IDs {invalid_review_ids}"
            )

        competitor_ids = pain_point.get("competitor_ids", [])
        unknown_competitors = sorted(
            item for item in competitor_ids if item not in valid_competitor_ids
        )
        if unknown_competitors:
            errors.append(
                f"{path}: unknown competitor_ids {unknown_competitors}"
            )

        evidence_competitors = {
            review_to_competitor[item]
            for item in evidence_ids
            if item in review_to_competitor
        }
        missing_competitors = sorted(evidence_competitors.difference(competitor_ids))
        if missing_competitors:
            errors.append(
                f"{path}: competitor_ids do not cover review evidence owners "
                f"{missing_competitors}"
            )

    opportunity_map = {
        item.get("opportunity_id"): item
        for item in competitor_analysis.get("differentiation_opportunities", [])
        if isinstance(item, dict)
        and isinstance(item.get("opportunity_id"), str)
        and item.get("opportunity_id")
    }

    for position, recommendation in enumerate(recommendations):
        path = f"recommendations[{position}]"
        related_pain_ids = recommendation.get("related_pain_point_ids", [])
        related_opportunity_ids = recommendation.get(
            "related_opportunity_ids", []
        )
        unknown_pain_ids = sorted(
            item for item in related_pain_ids if item not in pain_point_map
        )
        unknown_opportunity_ids = sorted(
            item for item in related_opportunity_ids if item not in opportunity_map
        )
        if unknown_pain_ids:
            errors.append(
                f"{path}: recommendation references unknown pain points "
                f"{unknown_pain_ids}"
            )
        if unknown_opportunity_ids:
            errors.append(
                f"{path}: recommendation references unknown opportunities "
                f"{unknown_opportunity_ids}"
            )

        valid_pain_ids = [
            item for item in related_pain_ids if item in pain_point_map
        ]
        valid_opportunity_ids = [
            item for item in related_opportunity_ids if item in opportunity_map
        ]
        if not valid_pain_ids and not valid_opportunity_ids:
            errors.append(
                f"{path}: recommendation has no valid pain-point or opportunity link"
            )
            unsupported_claim_count += 1
            continue
        if not valid_pain_ids:
            warnings.append(
                f"{path}: recommendation is supported by an opportunity but has "
                "no pain-point link"
            )

        supporting_evidence: set[str] = set()
        for pain_id in valid_pain_ids:
            supporting_evidence.update(
                pain_point_map[pain_id].get("evidence_ids", [])
            )
        for opportunity_id in valid_opportunity_ids:
            supporting_evidence.update(
                opportunity_map[opportunity_id].get("evidence_ids", [])
            )
        recommendation_evidence = set(recommendation.get("evidence_ids", []))
        if supporting_evidence and not recommendation_evidence.intersection(
            supporting_evidence
        ):
            errors.append(
                f"{path}: evidence_ids do not overlap evidence from linked insights"
            )
            unsupported_claim_count += 1

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "unsupported_claim_count": unsupported_claim_count,
    }


def _build_evidence_index(
    analysis_output: dict[str, Any],
) -> dict[str, Any]:
    product_input = analysis_output.get("product_input", {})
    competitor_base = analysis_output.get("competitor_analysis_base", {})
    review_analysis = analysis_output.get("review_analysis", {})

    product_ids = {
        product_input.get("product_id")
    } if isinstance(product_input, dict) else set()
    product_ids.discard(None)

    competitor_ids: set[str] = set()
    if isinstance(competitor_base, dict):
        for row in competitor_base.get("competitor_matrix", []):
            if isinstance(row, dict) and isinstance(row.get("competitor_id"), str):
                competitor_ids.add(row["competitor_id"])

    review_ids: set[str] = set()
    review_to_competitor: dict[str, str] = {}
    if isinstance(review_analysis, dict):
        for record in review_analysis.get("evidence_records", []):
            if not isinstance(record, dict):
                continue
            review_id = record.get("review_id")
            competitor_id = record.get("competitor_id")
            if isinstance(review_id, str) and isinstance(competitor_id, str):
                review_ids.add(review_id)
                review_to_competitor[review_id] = competitor_id

    return {
        "product_ids": product_ids,
        "competitor_ids": competitor_ids,
        "review_ids": review_ids,
        "review_to_competitor": review_to_competitor,
        "all_ids": product_ids | competitor_ids | review_ids,
    }


def _walk_claims(value: Any, path: str = "$") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        if value.get("source_type") in {
            "data_fact",
            "calculated",
            "ai_inference",
            "recommendation",
        }:
            yield path, value
        for key, child in value.items():
            yield from _walk_claims(child, f"{path}.{key}")
    elif isinstance(value, list):
        for position, child in enumerate(value):
            yield from _walk_claims(child, f"{path}[{position}]")

