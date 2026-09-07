"""Strategy-recommendation presentation component."""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.components.evidence_validator import render_claim_evidence


TYPE_LABELS = {
    "product_improvement": "产品改进",
    "listing_optimization": "Listing 优化",
    "positioning": "定位建议",
}


def render_recommendations(report: dict[str, Any]) -> None:
    recommendations = sorted(
        report["recommendations"],
        key=lambda item: {"P0": 0, "P1": 1, "P2": 2}.get(item["priority"], 9),
    )
    if not recommendations:
        st.info("当前没有通过验证的策略建议。")
        return

    for item in recommendations:
        with st.container(border=True):
            st.subheader(f"{item['priority']} · {item['title']}")
            st.caption(
                f"{TYPE_LABELS.get(item['type'], item['type'])}　｜　"
                f"用户价值：{item['user_value']}　｜　"
                f"实施难度：{item['implementation_effort']}"
            )
            st.write(item["content"])
            st.write(f"风险提示：{item['risk_note']}")
            links = item["related_pain_point_ids"] + item["related_opportunity_ids"]
            st.caption(f"关联洞察：{', '.join(links)}")
            render_claim_evidence(item)
