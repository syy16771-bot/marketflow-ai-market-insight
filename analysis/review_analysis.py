"""Deterministic review statistics and keyword signals for MarketFlow AI."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_COLUMNS = {
    "review_id",
    "competitor_id",
    "rating",
    "review_text",
    "review_language",
    "source_type",
    "is_synthetic",
}

# These rules produce review signals for later AI interpretation. They are not
# semantic conclusions and must not be presented as validated user insights.
THEME_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("cleaning", "清洁难度", ("clean", "cleaning", "scrub", "wash", "blade", "hair", "corner")),
    ("performance", "性能不足", ("stuck", "blend", "frozen", "power", "weak")),
    ("leakage", "密封与漏液", ("leak", "leaked", "lid", "spill")),
    ("battery", "续航与充电", ("battery", "charge", "charging")),
    ("noise", "运行噪音", ("loud", "noise", "noisy", "pump")),
    ("filter_cost", "滤芯与维护成本", ("filter", "replacement", "cost")),
    ("durability", "耐用性", ("flatten", "flattened", "broke", "broken", "deform")),
    ("heat", "闷热与散热", ("warm", "hot", "heat", "cooler")),
    ("size_fit", "尺寸适配", ("wide", "small chair", "too small", "too large", "fit")),
    ("support", "支撑体验", ("support", "firm", "upright", "soft")),
    ("portability", "重量与便携", ("heavy", "weight", "portable", "bag")),
)


def load_reviews(path: str | Path) -> list[dict[str, Any]]:
    """Load reviews.csv and normalize ratings and booleans."""
    source_path = Path(path)
    with source_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS.difference(columns)
        if missing:
            raise ValueError(f"{source_path} is missing columns: {sorted(missing)}")
        raw_records = list(reader)

    if not raw_records:
        raise ValueError(f"{source_path} must contain at least one review")

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_records, start=2):
        review_id = (raw.get("review_id") or "").strip()
        competitor_id = (raw.get("competitor_id") or "").strip()
        review_text = (raw.get("review_text") or "").strip()
        if not review_id or not competitor_id or not review_text:
            raise ValueError(f"Review row {index} has an empty required value")
        if review_id in seen_ids:
            raise ValueError(f"Duplicate review_id: {review_id}")
        seen_ids.add(review_id)

        try:
            rating = int(raw["rating"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"{review_id}.rating must be an integer") from error
        if rating < 1 or rating > 5:
            raise ValueError(f"{review_id}.rating must be between 1 and 5")

        records.append(
            {
                "review_id": review_id,
                "competitor_id": competitor_id,
                "rating": rating,
                "review_text": review_text,
                "review_language": (raw.get("review_language") or "").strip(),
                "data_source_type": (raw.get("source_type") or "").strip(),
                "is_synthetic": _parse_boolean(raw.get("is_synthetic"), review_id),
            }
        )
    return records


def analyze_reviews(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate review metrics and deterministic pain-point signals."""
    if not reviews:
        raise ValueError("At least one review is required")

    all_review_ids = [item["review_id"] for item in reviews]
    ratings = [item["rating"] for item in reviews]
    negative_reviews = [item for item in reviews if item["rating"] <= 3]
    rating_distribution = {str(star): 0 for star in range(1, 6)}
    rating_distribution.update(
        {str(star): count for star, count in sorted(Counter(ratings).items())}
    )

    competitor_counts = Counter(item["competitor_id"] for item in reviews)
    competitor_review_counts = [
        {
            "competitor_id": competitor_id,
            "count": count,
            "evidence_ids": [
                item["review_id"]
                for item in reviews
                if item["competitor_id"] == competitor_id
            ],
            "confidence": 1,
            "source_type": "calculated",
        }
        for competitor_id, count in sorted(competitor_counts.items())
    ]

    theme_matches: dict[str, list[dict[str, Any]]] = {
        theme_id: [] for theme_id, _, _ in THEME_RULES
    }
    matched_review_ids: set[str] = set()
    for review in negative_reviews:
        normalized_text = review["review_text"].lower()
        for theme_id, _, keywords in THEME_RULES:
            if any(keyword in normalized_text for keyword in keywords):
                theme_matches[theme_id].append(review)
                matched_review_ids.add(review["review_id"])

    labels = {theme_id: label for theme_id, label, _ in THEME_RULES}
    pain_point_signals = []
    for theme_id, matched in theme_matches.items():
        if not matched:
            continue
        evidence_ids = [item["review_id"] for item in matched]
        ratio = len(matched) / max(len(negative_reviews), 1)
        pain_point_signals.append(
            {
                "signal_id": f"signal-{theme_id}",
                "theme": theme_id,
                "label": labels[theme_id],
                "match_method": "keyword_rule",
                "count": len(matched),
                "frequency_level": _frequency_level(ratio),
                "sample_size": len(reviews),
                "negative_sample_size": len(negative_reviews),
                "competitor_ids": sorted(
                    {item["competitor_id"] for item in matched}
                ),
                "evidence_ids": evidence_ids,
                "confidence": 1,
                "source_type": "calculated",
            }
        )

    pain_point_signals.sort(key=lambda item: (-item["count"], item["theme"]))
    evidence_records = [
        {
            **review,
            "evidence_ids": [review["review_id"]],
            "confidence": 1,
            "source_type": "data_fact",
        }
        for review in reviews
    ]

    return {
        "review_statistics": {
            "total_reviews": len(reviews),
            "negative_review_count": len(negative_reviews),
            "average_rating": round(sum(ratings) / len(ratings), 2),
            "rating_distribution": rating_distribution,
            "evidence_ids": all_review_ids,
            "confidence": 1,
            "source_type": "calculated",
        },
        "competitor_review_counts": competitor_review_counts,
        "pain_point_signals": pain_point_signals,
        "unclassified_negative_review_ids": sorted(
            item["review_id"]
            for item in negative_reviews
            if item["review_id"] not in matched_review_ids
        ),
        "evidence_records": evidence_records,
    }


def _frequency_level(ratio: float) -> str:
    if ratio >= 0.4:
        return "high"
    if ratio >= 0.2:
        return "medium"
    return "low"


def _parse_boolean(value: str | None, review_id: str) -> bool:
    normalized = (value or "").strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{review_id}.is_synthetic must be true or false")

