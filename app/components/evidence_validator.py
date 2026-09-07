"""Evidence and trust explanations for the Streamlit presentation layer."""

from __future__ import annotations

from typing import Any

import streamlit as st


SOURCE_LABELS = {
    "data_fact": "Data Fact · 原始事实",
    "calculated": "Calculated · 确定性计算",
    "ai_inference": "AI Inference · AI 推断",
    "recommendation": "Recommendation · 策略建议",
}


def render_claim_evidence(claim: dict[str, Any]) -> None:
    """Render provenance shared by insight cards."""
    source_type = claim.get("source_type", "unknown")
    confidence = claim.get("confidence")
    evidence_ids = claim.get("evidence_ids", [])
    label = SOURCE_LABELS.get(source_type, source_type)
    confidence_text = (
        f"{float(confidence):.0%}" if isinstance(confidence, (int, float)) else "—"
    )
    st.caption(
        f"来源：{label}　｜　置信度：{confidence_text}　｜　"
        f"证据：{', '.join(evidence_ids) if evidence_ids else '无'}"
    )


def render_trust_page(report: dict[str, Any] | None) -> None:
    """Render source taxonomy, validation state, sources, and limitations."""
    st.title("可信度说明")
    st.write("每条结论都标注来源类型、证据 ID 和置信度，便于区分事实与判断。")

    definitions = [
        ("Data Fact", "来自内置商品、竞品或评论样本的原始字段，不由模型生成。"),
        ("Calculated", "由确定性分析层计算，例如价格区间、评论数和痛点频次。"),
        ("AI Inference", "基于已提供证据形成的商品定位、用户洞察或差异机会。"),
        ("Recommendation", "基于已验证痛点或机会形成的产品与 Listing 行动建议。"),
    ]
    columns = st.columns(2)
    for index, (title, description) in enumerate(definitions):
        with columns[index % 2]:
            with st.container(border=True):
                st.subheader(title)
                st.write(description)

    st.subheader("数据来源")
    if report:
        dataset = report.get("dataset", {})
        st.write(
            f"数据集：`{dataset.get('dataset_id', '—')}`　｜　"
            f"版本：`{dataset.get('dataset_version', '—')}`　｜　"
            f"类型：`{dataset.get('data_source_type', '—')}`"
        )
        st.caption(report.get("disclaimer", ""))
    else:
        st.info("尚未加载报告，当前项目使用内置 JSON/CSV 模拟数据。")

    st.subheader("验证状态")
    if report:
        summary = report.get("validation_summary", {})
        cols = st.columns(4)
        cols[0].metric("Schema", "通过" if summary.get("schema_valid") else "失败")
        cols[1].metric(
            "Evidence", "通过" if summary.get("evidence_ids_valid") else "失败"
        )
        cols[2].metric(
            "Calculated", "一致" if summary.get("calculations_verified") else "异常"
        )
        cols[3].metric("Unsupported", summary.get("unsupported_claim_count", 0))
        for warning in summary.get("warnings", []):
            st.warning(warning)

    st.subheader("已知限制")
    st.markdown(
        """
- 当前仅覆盖三个内置 Demo，不能代表真实市场总体。
- 不包含实时网页搜索、Amazon API、销量、收入或市场规模预测。
- 评论频次只描述当前小样本，不可外推为平台级趋势。
- AI 推断与建议必须结合置信度和证据阅读，不能替代真实用户研究。
"""
    )
