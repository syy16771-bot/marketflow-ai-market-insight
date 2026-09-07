"""MarketFlow AI portfolio interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FINAL_REPORT_PATH = PROJECT_ROOT / "pipeline" / "final_report.json"
FINAL_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "final_report.schema.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.components.competitor_analysis import render_competitor_analysis
from app.components.evidence_validator import render_claim_evidence, render_trust_page
from app.components.pain_point_analysis import render_pain_points
from app.components.product_analysis import render_product_analysis
from app.components.recommendations import render_recommendations
from llm_client.config import LLMConfig, LLMConfigError
from pipeline.run_pipeline import DEMO_SLUGS, PipelineValidationError, run_demo_pipeline
from validation.schema_validator import validate_json_schema


DEMO_LABELS = {
    "portable-blender": "Portable Blender｜便携榨汁杯",
    "pet-water-fountain": "Pet Water Fountain｜宠物饮水机",
    "ergonomic-seat-cushion": "Ergonomic Seat Cushion｜人体工学坐垫",
}


st.set_page_config(
    page_title="MarketFlow AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    if "report" not in st.session_state:
        report, load_error = _load_existing_report()
        st.session_state.report = report
        st.session_state.report_load_error = load_error

    with st.sidebar:
        st.title("MarketFlow AI")
        st.caption("跨境电商市场洞察助手")
        page = st.radio(
            "导航",
            ("分析工作台", "结果报告", "可信度说明"),
            label_visibility="collapsed",
        )
        st.divider()
        _render_runtime_status()

    if page == "分析工作台":
        _render_workspace()
    elif page == "结果报告":
        _render_report_page(st.session_state.report)
    else:
        render_trust_page(st.session_state.report)


def _render_workspace() -> None:
    st.title("AI 跨境电商市场洞察")
    st.write("从商品信息出发，形成可追溯的竞品、用户痛点与产品策略报告。")

    demo_slug = st.selectbox(
        "Demo 商品",
        DEMO_SLUGS,
        format_func=lambda value: DEMO_LABELS[value],
    )
    demo_product = _load_demo_product(demo_slug)

    left, right = st.columns(2)
    with left:
        product_name = st.text_input(
            "商品名称",
            value=demo_product["product_name"],
            key=f"product_name_{demo_slug}",
        )
    with right:
        target_market = st.text_input(
            "目标市场",
            value=demo_product["target_market"],
            key=f"target_market_{demo_slug}",
        )
    description = st.text_area(
        "商品描述",
        value=demo_product["description"],
        height=130,
        key=f"description_{demo_slug}",
    )
    st.caption(
        "当前 MVP 使用固定 Demo 数据包。编辑字段可用于体验输入设计，但只有原始 "
        "Demo 信息具备对应竞品与评论证据。"
    )

    if st.button("开始分析", type="primary", use_container_width=True):
        current_input = (product_name.strip(), target_market.strip(), description.strip())
        demo_input = (
            demo_product["product_name"].strip(),
            demo_product["target_market"].strip(),
            demo_product["description"].strip(),
        )
        if current_input != demo_input:
            st.warning(
                "当前输入与内置 Demo 不一致，缺少配套竞品和评论证据，因此未启动分析。"
            )
            return

        try:
            config = LLMConfig.from_env()
            with st.spinner("正在执行分析与验证 Pipeline…"):
                result = run_demo_pipeline(
                    demo_slug,
                    output_path=FINAL_REPORT_PATH,
                    config=config,
                )
        except LLMConfigError as error:
            st.error(f"LLM 配置无效：{error}")
        except PipelineValidationError as error:
            st.error("验证未通过，最终报告未生成。")
            for item in error.errors:
                st.code(item)
        except Exception as error:
            st.error(f"Pipeline 已停止：{error}")
        else:
            st.session_state.report = _repair_display_text(result["final_report"])
            st.session_state.report_load_error = None
            st.success(
                f"分析完成：{result['mode']} 模式，"
                f"总耗时 {result['timings_ms']['total_ms']:.1f} ms。"
                "请前往“结果报告”查看。"
            )

    existing = st.session_state.report
    if existing:
        snapshot = existing["input_snapshot"]
        st.info(
            f"已优先加载现有报告：{snapshot['product_name']} · "
            f"{existing['generated_at']}"
        )
    elif st.session_state.report_load_error:
        st.warning(st.session_state.report_load_error)


def _render_report_page(report: dict[str, Any] | None) -> None:
    st.title("市场洞察报告")
    if not report:
        st.info("暂无有效报告。请先在“分析工作台”运行一个 Demo。")
        return

    snapshot = report["input_snapshot"]
    st.subheader(snapshot["product_name"])
    st.caption(
        f"目标市场：{snapshot['target_market']}　｜　"
        f"报告状态：{report['analysis_status']}　｜　"
        f"生成时间：{report['generated_at']}"
    )
    render_claim_evidence(snapshot)

    dataset = report["dataset"]
    high_priority_pains = sum(
        pain.get("severity", {}).get("level") == "high"
        for pain in report["pain_points"]
    )
    metrics = st.columns(4)
    metrics[0].metric("竞品数量", dataset["competitor_count"])
    metrics[1].metric("评论数量", dataset["review_count"])
    metrics[2].metric("高优先级痛点", high_priority_pains)
    metrics[3].metric("优化建议", len(report["recommendations"]))

    tabs = st.tabs(("商品分析", "竞品分析", "用户痛点", "优化建议"))
    with tabs[0]:
        render_product_analysis(report)
    with tabs[1]:
        render_competitor_analysis(report)
    with tabs[2]:
        render_pain_points(report)
    with tabs[3]:
        render_recommendations(report)


def _render_runtime_status() -> None:
    try:
        config = LLMConfig.from_env()
    except LLMConfigError as error:
        st.error("LLM 配置未就绪")
        st.caption(str(error))
        return
    mode = "Mock 模式" if config.mock_mode else "真实 LLM 模式"
    st.caption(f"运行模式：{mode}")
    if not config.mock_mode:
        st.caption(f"模型：{config.model}")


def _load_existing_report() -> tuple[dict[str, Any] | None, str | None]:
    if not FINAL_REPORT_PATH.exists():
        return None, None
    try:
        report = _load_json(FINAL_REPORT_PATH)
        result = validate_json_schema(report, FINAL_SCHEMA_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return None, f"已有 final_report.json 无法读取：{error}"
    if not result["valid"]:
        return None, "已有 final_report.json 未通过 Schema 校验，因此未展示。"
    return _repair_display_text(report), None


def _load_demo_product(demo_slug: str) -> dict[str, Any]:
    return _repair_display_text(_load_json(DATA_DIR / demo_slug / "product.json"))


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _repair_display_text(value: Any) -> Any:
    """Repair legacy mojibake for display without changing source data."""
    if isinstance(value, dict):
        return {key: _repair_display_text(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_repair_display_text(item) for item in value]
    if not isinstance(value, str):
        return value

    candidates = [value]
    for decoding in ("utf-8", "gb18030"):
        try:
            candidates.append(value.encode("latin-1").decode(decoding))
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return max(candidates, key=_text_quality_score)


def _text_quality_score(value: str) -> int:
    cjk = sum("\u4e00" <= character <= "\u9fff" for character in value)
    suspicious = sum(character in "ÃÂäåæçèéðñòóôõöøùúûüýþÿ" for character in value)
    replacement = value.count("�")
    return cjk * 3 - suspicious * 2 - replacement * 5


if __name__ == "__main__":
    main()
