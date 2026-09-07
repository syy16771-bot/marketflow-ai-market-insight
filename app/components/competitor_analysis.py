"""Competitor-analysis presentation component."""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.components.evidence_validator import render_claim_evidence


def render_competitor_analysis(report: dict[str, Any]) -> None:
    analysis = report["competitor_analysis"]
    price = analysis["price_range"]

    st.subheader("价格区间")
    cols = st.columns(4)
    currency = price["currency"]
    cols[0].metric("最低价", f"{currency} {price['minimum']:.2f}")
    cols[1].metric("中位价", f"{currency} {price['median']:.2f}")
    cols[2].metric("最高价", f"{currency} {price['maximum']:.2f}")
    cols[3].metric("竞品样本", price["sample_size"])
    render_claim_evidence(price)

    st.subheader("竞品矩阵")
    rows = []
    for item in analysis["competitor_matrix"]:
        rows.append(
            {
                "竞品": item["name"],
                "价格": f"{item['currency']} {item['price']:.2f}",
                "评分": item["rating"],
                "评论数": item["review_count"],
                "功能": " / ".join(item["features"]),
                "卖点": " / ".join(item["selling_points"]),
                "来源": "Data Fact",
                "证据 ID": ", ".join(item["evidence_ids"]),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    left, right = st.columns(2)
    with left:
        _render_insight_group("优势", analysis["strengths"])
    with right:
        _render_insight_group("不足", analysis["weaknesses"])
    _render_insight_group(
        "差异机会", analysis["differentiation_opportunities"]
    )


def _render_insight_group(title: str, items: list[dict[str, Any]]) -> None:
    st.subheader(title)
    if not items:
        st.info("当前没有足够证据形成结论。")
        return
    for item in items:
        with st.container(border=True):
            st.markdown(f"**{item['title']}**")
            st.write(item["description"])
            render_claim_evidence(item)
