"""Customer pain-point presentation component."""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.components.evidence_validator import render_claim_evidence


def render_pain_points(report: dict[str, Any]) -> None:
    pain_points = report["pain_points"]
    if not pain_points:
        st.info("当前样本没有形成可验证的痛点。")
        return

    for pain in pain_points:
        frequency = pain["frequency"]
        severity = pain["severity"]
        with st.container(border=True):
            st.subheader(pain["name"])
            st.write(pain["description"])
            cols = st.columns(4)
            cols[0].metric("频次", frequency["count"])
            cols[1].metric("频率等级", frequency["level"])
            cols[2].metric("严重程度", severity["level"])
            cols[3].metric("证据状态", pain["evidence_status"])
            st.caption(f"影响场景：{' / '.join(pain['affected_scenarios'])}")
            st.write(f"严重性判断：{severity['reason']}")
            render_claim_evidence(pain)
            with st.expander("查看频次计算依据"):
                st.write(
                    f"样本量 {frequency['sample_size']}，命中 "
                    f"{frequency['count']} 条评论。"
                )
                render_claim_evidence(frequency)
