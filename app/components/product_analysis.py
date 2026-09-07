"""Product-insight presentation component."""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.components.evidence_validator import render_claim_evidence


def render_product_analysis(report: dict[str, Any]) -> None:
    analysis = report["product_analysis"]

    st.subheader("商品定位")
    positioning = analysis["positioning"]
    st.write(positioning["content"])
    render_claim_evidence(positioning)

    _render_claim_list("目标用户", analysis["target_users"])
    _render_claim_list("使用场景", analysis["use_scenarios"])
    _render_claim_list("核心卖点", analysis["selling_points"])

    st.subheader("信息缺口")
    for gap in analysis["information_gaps"]:
        with st.expander(f"{gap['field']} · 影响 {gap['impact']}"):
            st.write(gap["reason"])
            render_claim_evidence(gap)


def _render_claim_list(title: str, claims: list[dict[str, Any]]) -> None:
    st.subheader(title)
    if not claims:
        st.info("当前没有足够证据形成该类结论。")
        return
    for claim in claims:
        with st.container(border=True):
            st.markdown(f"**{claim['name']}**")
            st.write(claim["description"])
            render_claim_evidence(claim)
