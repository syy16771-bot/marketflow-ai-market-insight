"""Run MarketFlow AI with mock outputs or an OpenAI-compatible LLM."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
MOCK_DIR = PIPELINE_DIR / "mock_llm_outputs"
DEFAULT_OUTPUT = PIPELINE_DIR / "final_report.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.output_schema import build_deterministic_output
from llm.customer_insight import build_customer_insight_package
from llm.product_insight import build_product_insight_package
from llm.strategy_advisor import build_strategy_advisor_package
from llm_client.client import OpenAICompatibleClient
from llm_client.config import LLMConfig
from validation.consistency_checker import (
    check_consistency,
    validate_for_final_report,
)
from validation.evidence_validator import validate_evidence
from validation.schema_validator import validate_json_schema


DEMO_SLUGS = (
    "portable-blender",
    "pet-water-fountain",
    "ergonomic-seat-cushion",
)


class PipelineValidationError(Exception):
    """Raised when validation blocks final-report generation."""

    def __init__(self, demo_slug: str, errors: list[str]):
        self.demo_slug = demo_slug
        self.errors = errors
        super().__init__(f"{demo_slug}: validation failed: {'; '.join(errors)}")


def run_demo_pipeline(
    demo_slug: str,
    output_path: str | Path | None = None,
    config: LLMConfig | None = None,
) -> dict[str, Any]:
    """Run one Demo through analysis, LLM selection, validation, and assembly."""
    if demo_slug not in DEMO_SLUGS:
        raise ValueError(f"Unknown Demo {demo_slug!r}; choose from {DEMO_SLUGS}")

    total_started = perf_counter()
    timings: dict[str, float] = {}
    runtime_config = config or LLMConfig.from_env()

    started = perf_counter()
    analysis_output = build_deterministic_output(DATA_DIR / demo_slug)
    timings["analysis_ms"] = _elapsed_ms(started)

    started = perf_counter()
    if runtime_config.mock_mode:
        outputs = _load_mock_outputs(demo_slug)
        timing_key = "mock_llm_ms"
    else:
        outputs = _generate_real_outputs(
            demo_slug, analysis_output, runtime_config
        )
        timing_key = "llm_ms"
    product_analysis = outputs["product_analysis"]
    competitor_analysis = outputs["competitor_analysis"]
    pain_points = outputs["pain_points"]
    recommendations = outputs["recommendations"]
    timings[timing_key] = _elapsed_ms(started)

    started = perf_counter()
    schema_results = _validate_component_schemas(
        product_analysis,
        competitor_analysis,
        pain_points,
        recommendations,
    )
    timings["schema_validation_ms"] = _elapsed_ms(started)

    started = perf_counter()
    evidence_result = validate_evidence(
        analysis_output,
        product_analysis,
        competitor_analysis,
        pain_points,
        recommendations,
    )
    timings["evidence_validation_ms"] = _elapsed_ms(started)

    started = perf_counter()
    consistency_result = check_consistency(
        analysis_output,
        competitor_analysis,
        pain_points,
    )
    timings["consistency_check_ms"] = _elapsed_ms(started)

    validation_errors = []
    for label, result in schema_results.items():
        validation_errors.extend(
            f"schema:{label}: {error}" for error in result["errors"]
        )
    validation_errors.extend(
        f"evidence: {error}" for error in evidence_result["errors"]
    )
    validation_errors.extend(
        f"consistency: {error}" for error in consistency_result["errors"]
    )
    if validation_errors:
        raise PipelineValidationError(demo_slug, validation_errors)

    started = perf_counter()
    validation_summary, gate_errors = validate_for_final_report(
        analysis_output,
        product_analysis,
        competitor_analysis,
        pain_points,
        recommendations,
    )
    if validation_summary is None:
        raise PipelineValidationError(demo_slug, gate_errors)

    final_report = _build_final_report(
        demo_slug,
        analysis_output,
        product_analysis,
        competitor_analysis,
        pain_points,
        recommendations,
        validation_summary,
    )
    final_schema_result = validate_json_schema(
        final_report, SCHEMAS_DIR / "final_report.schema.json"
    )
    if not final_schema_result["valid"]:
        raise PipelineValidationError(
            demo_slug,
            [f"schema:final_report: {item}" for item in final_schema_result["errors"]],
        )

    if output_path is not None:
        _write_json_atomic(Path(output_path), final_report)
    timings["final_report_ms"] = _elapsed_ms(started)
    timings["total_ms"] = _elapsed_ms(total_started)

    return {
        "demo": demo_slug,
        "success": True,
        "mode": "mock" if runtime_config.mock_mode else "llm",
        "timings_ms": timings,
        "validation_summary": validation_summary,
        "final_report": final_report,
        "output_path": str(Path(output_path).resolve())
        if output_path is not None
        else None,
    }


def run_all_demos() -> list[dict[str, Any]]:
    """Run all three reports in memory without creating three output files."""
    return [run_demo_pipeline(demo_slug) for demo_slug in DEMO_SLUGS]


def _load_mock_outputs(demo_slug: str) -> dict[str, Any]:
    product_catalog = _load_json(MOCK_DIR / "product_analysis.json")
    customer_catalog = _load_json(MOCK_DIR / "customer_insight.json")
    strategy_catalog = _load_json(MOCK_DIR / "strategy_output.json")
    product_analysis = _require_demo(
        product_catalog, demo_slug, "product analysis"
    )
    customer_insight = _require_demo(
        customer_catalog, demo_slug, "customer insight"
    )
    recommendations = _require_demo(
        strategy_catalog, demo_slug, "strategy output"
    )
    competitor_analysis, pain_points = _split_customer_insight(
        demo_slug, customer_insight
    )
    if not isinstance(recommendations, list):
        raise ValueError(f"{demo_slug}: strategy output must be an array")
    return {
        "product_analysis": product_analysis,
        "competitor_analysis": competitor_analysis,
        "pain_points": pain_points,
        "recommendations": recommendations,
    }


def _generate_real_outputs(
    demo_slug: str,
    analysis_output: dict[str, Any],
    config: LLMConfig,
) -> dict[str, Any]:
    """Generate sequentially, blocking strategy when upstream validation fails."""
    client = OpenAICompatibleClient(config)

    product_analysis = client.generate_json(
        build_product_insight_package(analysis_output)
    )
    product_schema = validate_json_schema(
        product_analysis, SCHEMAS_DIR / "product_analysis.schema.json"
    )
    if not product_schema["valid"]:
        raise PipelineValidationError(
            demo_slug,
            [f"schema:product_analysis: {item}" for item in product_schema["errors"]],
        )

    customer_insight = client.generate_json(
        build_customer_insight_package(analysis_output)
    )
    competitor_analysis, pain_points = _split_customer_insight(
        demo_slug, customer_insight
    )

    upstream_schemas = _validate_component_schemas(
        product_analysis, competitor_analysis, pain_points, []
    )
    upstream_errors = [
        f"schema:{label}: {error}"
        for label, result in upstream_schemas.items()
        for error in result["errors"]
    ]
    if upstream_errors:
        raise PipelineValidationError(demo_slug, upstream_errors)

    evidence_result = validate_evidence(
        analysis_output,
        product_analysis,
        competitor_analysis,
        pain_points,
        [],
    )
    consistency_result = check_consistency(
        analysis_output, competitor_analysis, pain_points
    )
    upstream_errors.extend(
        f"evidence: {error}" for error in evidence_result["errors"]
    )
    upstream_errors.extend(
        f"consistency: {error}" for error in consistency_result["errors"]
    )
    if upstream_errors:
        raise PipelineValidationError(demo_slug, upstream_errors)

    recommendations = client.generate_json(
        build_strategy_advisor_package(
            analysis_output,
            product_analysis,
            competitor_analysis,
            pain_points,
        )
    )
    if not isinstance(recommendations, list):
        raise PipelineValidationError(
            demo_slug, ["schema:strategy output must be an array"]
        )
    return {
        "product_analysis": product_analysis,
        "competitor_analysis": competitor_analysis,
        "pain_points": pain_points,
        "recommendations": recommendations,
    }


def _split_customer_insight(
    demo_slug: str, customer_insight: Any
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(customer_insight, dict):
        raise PipelineValidationError(
            demo_slug, ["schema:customer insight must be an object"]
        )
    competitor_analysis = customer_insight.get("competitor_analysis")
    pain_points = customer_insight.get("pain_points")
    errors = []
    if not isinstance(competitor_analysis, dict):
        errors.append("schema:customer insight competitor_analysis must be an object")
    if not isinstance(pain_points, list) or any(
        not isinstance(item, dict) for item in pain_points
    ):
        errors.append("schema:customer insight pain_points must be an object array")
    if errors:
        raise PipelineValidationError(demo_slug, errors)
    return competitor_analysis, pain_points


def _validate_component_schemas(
    product_analysis: dict[str, Any],
    competitor_analysis: dict[str, Any],
    pain_points: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    results = {
        "product_analysis": validate_json_schema(
            product_analysis, SCHEMAS_DIR / "product_analysis.schema.json"
        ),
        "competitor_analysis": validate_json_schema(
            competitor_analysis,
            SCHEMAS_DIR / "competitor_analysis.schema.json",
        ),
    }
    for position, pain_point in enumerate(pain_points):
        results[f"pain_points[{position}]"] = validate_json_schema(
            pain_point, SCHEMAS_DIR / "pain_point.schema.json"
        )
    for position, recommendation in enumerate(recommendations):
        results[f"recommendations[{position}]"] = validate_json_schema(
            recommendation, SCHEMAS_DIR / "recommendation.schema.json"
        )
    return results


def _build_final_report(
    demo_slug: str,
    analysis_output: dict[str, Any],
    product_analysis: dict[str, Any],
    competitor_analysis: dict[str, Any],
    pain_points: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    validation_summary: dict[str, Any],
) -> dict[str, Any]:
    product_input = analysis_output["product_input"]
    generated_at = datetime.now(timezone.utc).isoformat()
    executive_summary = [
        {
            "title": "商品定位",
            "content": product_analysis["positioning"]["content"],
            "evidence_ids": product_analysis["positioning"]["evidence_ids"],
            "confidence": product_analysis["positioning"]["confidence"],
            "source_type": "ai_inference",
        }
    ]
    opportunities = competitor_analysis["differentiation_opportunities"]
    if opportunities:
        opportunity = opportunities[0]
        executive_summary.append(
            {
                "title": opportunity["title"],
                "content": opportunity["description"],
                "evidence_ids": opportunity["evidence_ids"],
                "confidence": opportunity["confidence"],
                "source_type": "ai_inference",
            }
        )
    if recommendations:
        recommendation = recommendations[0]
        executive_summary.append(
            {
                "title": recommendation["title"],
                "content": recommendation["content"],
                "evidence_ids": recommendation["evidence_ids"],
                "confidence": recommendation["confidence"],
                "source_type": "recommendation",
            }
        )

    return {
        "report_id": f"marketflow-{demo_slug}-{generated_at}",
        "schema_version": "1.0.0",
        "generated_at": generated_at,
        "analysis_status": "complete",
        "dataset": analysis_output["dataset"],
        "input_snapshot": {
            "product_id": product_input["product_id"],
            "product_name": product_input["product_name"],
            "target_market": product_input["target_market"],
            "description": product_input["description"],
            "expected_price": product_input.get("expected_price"),
            "currency": product_input["currency"],
            "evidence_ids": [product_input["product_id"]],
            "confidence": 1,
            "source_type": "data_fact",
        },
        "executive_summary": executive_summary,
        "product_analysis": product_analysis,
        "competitor_analysis": competitor_analysis,
        "pain_points": pain_points,
        "recommendations": recommendations,
        "validation_summary": validation_summary,
        "disclaimer": product_input["disclaimer"],
    }


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _require_demo(catalog: dict[str, Any], demo_slug: str, label: str) -> Any:
    if not isinstance(catalog, dict) or demo_slug not in catalog:
        raise ValueError(f"{label} mock is missing Demo {demo_slug!r}")
    return catalog[demo_slug]


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temporary_path.replace(path)


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Test all Demos in memory")
    parser.add_argument(
        "--demo", choices=DEMO_SLUGS, default="portable-blender"
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT
    )
    args = parser.parse_args()

    if args.all:
        results = run_all_demos()
    else:
        results = [run_demo_pipeline(args.demo, args.output)]

    display = [
        {
            "demo": result["demo"],
            "success": result["success"],
            "mode": result["mode"],
            "timings_ms": result["timings_ms"],
            "validation_summary": result["validation_summary"],
            "output_path": result["output_path"],
        }
        for result in results
    ]
    print(json.dumps(display, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
