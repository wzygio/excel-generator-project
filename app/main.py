"""Streamlit UI entrypoint for the yield report workspace."""

from __future__ import annotations

import logging
from datetime import datetime
from hashlib import md5
from pathlib import Path
from typing import Any

import streamlit as st

from app.utils.app_setup import initialize_app, print_startup_banner
from yield_report.application.analysis_orchestrator import AnalysisOrchestrator
from yield_report.application.orchestrator import (
    DataAcquisitionOrchestrator,
    UserQueryResult,
)

logger = logging.getLogger(__name__)
RESULT_AREA_HEIGHT = 320


st.set_page_config(
    page_title="良率日报工作台",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def init_app() -> Any:
    """Initialize application configuration once per Streamlit process."""
    config = initialize_app()
    print_startup_banner(config)
    return config


def init_download_orchestrator() -> DataAcquisitionOrchestrator:
    """Create a fresh report-download orchestrator for each execution."""
    return DataAcquisitionOrchestrator()


@st.cache_resource
def init_analysis_orchestrator() -> AnalysisOrchestrator:
    """Create the data-analysis orchestrator."""
    return AnalysisOrchestrator()


def _init_session_state() -> None:
    defaults: dict[str, Any] = {
        "download_result_text": "",
        "analysis_result_text": "",
        "report_result_text": "",
        "download_logs": [],
        "analysis_logs": [],
        "report_logs": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _append_log(log_key: str, message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state[log_key].append(f"{timestamp} [{level}] {message}")


def _render_logs(log_key: str) -> None:
    with st.expander("日志", expanded=False):
        logs = st.session_state.get(log_key, [])
        st.code("\n".join(logs[-80:]) if logs else "暂无日志", language="text")


def _render_result_area(
    label: str,
    source_key: str,
    widget_key: str,
    height: int = RESULT_AREA_HEIGHT,
) -> None:
    text = st.session_state.get(source_key, "")
    content_hash = md5(text.encode("utf-8")).hexdigest()[:8]
    st.text_area(
        label,
        value=text,
        height=height,
        disabled=True,
        key=f"{widget_key}_{content_hash}",
        label_visibility="collapsed",
    )


def _format_download_result(result: UserQueryResult) -> str:
    request = result.parsed_request
    lines = [
        result.summary,
        "",
        "解析结果",
        f"- 报表类型: {request.report_type.value if request.report_type else '未指定'}",
        f"- 开始日期: {request.start_date or '未指定'}",
        f"- 结束日期: {request.end_date or '未指定'}",
        f"- 产品型号: {', '.join(request.product_models) if request.product_models else '未指定'}",
        f"- 用户意图: {request.user_intent or '未指定'}",
    ]
    if request.uncertainty_notes:
        lines.append(f"- 不确定信息: {request.uncertainty_notes}")

    lines.extend(["", "下载结果"])
    for item in result.results:
        status = "成功" if item.success else "失败"
        detail = str(item.file_path) if item.success and item.file_path else item.error_message
        lines.append(f"- {status}: {item.file_description} -> {detail}")

    return "\n".join(lines)


def _render_download_tab() -> None:
    st.markdown("#### 需求输入框")
    query = st.text_area(
        "报表下载需求",
        key="download_query",
        height=120,
        placeholder="我想要查询M678这款产品近两个月的良率",
    )

    if st.button("执行报表下载", type="primary", use_container_width=True):
        if not query.strip():
            st.session_state.download_result_text = "请输入报表下载需求。"
            _append_log("download_logs", "需求为空，未执行。", "WARN")
        else:
            _append_log("download_logs", f"开始处理需求: {query.strip()}")
            try:
                result = init_download_orchestrator().process_user_query(query.strip())
                st.session_state.download_result_text = _format_download_result(result)
                _append_log("download_logs", result.summary)
            except Exception as exc:
                logger.exception("报表下载流程失败")
                st.session_state.download_result_text = f"报表下载失败: {exc}"
                _append_log("download_logs", f"报表下载失败: {exc}", "ERROR")

    st.markdown("#### 结果")
    _render_result_area(
        "报表下载结果",
        source_key="download_result_text",
        widget_key="download_result_view",
    )
    _render_logs("download_logs")


def _render_analysis_tab() -> None:
    st.markdown("#### 需求输入框")
    query = st.text_area(
        "数据分析需求",
        key="analysis_query",
        height=120,
        placeholder="请分析M678近一个月日度良率变化趋势",
    )

    if st.button("执行数据分析", type="primary", use_container_width=True):
        if not query.strip():
            st.session_state.analysis_result_text = "请输入数据分析需求。"
            _append_log("analysis_logs", "需求为空，未执行。", "WARN")
        else:
            _append_log("analysis_logs", f"开始处理需求: {query.strip()}")
            try:
                result = init_analysis_orchestrator().analyze(query.strip())
                st.session_state.analysis_result_text = (
                    result.result_text if result.success else result.error_message
                )
                _append_log("analysis_logs", result.summary())
            except Exception as exc:
                logger.exception("数据分析流程失败")
                st.session_state.analysis_result_text = f"数据分析失败: {exc}"
                _append_log("analysis_logs", f"数据分析失败: {exc}", "ERROR")

    st.markdown("#### 结果")
    _render_result_area(
        "数据分析结果",
        source_key="analysis_result_text",
        widget_key="analysis_result_view",
    )
    _render_logs("analysis_logs")


def _render_report_tab() -> None:
    st.markdown("#### 需求输入框")
    request_text = st.text_area(
        "日报生成需求",
        key="report_query",
        height=120,
        placeholder="根据已下载源表生成今日良率日报",
    )

    if st.button("生成日报", type="primary", use_container_width=True):
        _append_log("report_logs", f"收到日报生成需求: {request_text.strip() or '未填写'}")
        st.session_state.report_result_text = "日报生成流程尚未接入 V2 编排器。"
        _append_log("report_logs", "日报生成流程尚未接入 V2 编排器。", "WARN")

    st.markdown("#### 结果")
    output_path = Path(APP_CONFIG.paths.output_dir) / APP_CONFIG.paths.output_file
    if output_path.exists():
        with output_path.open("rb") as file:
            st.download_button(
                "下载日报",
                data=file,
                file_name=APP_CONFIG.paths.output_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    _render_result_area(
        "日报生成结果",
        source_key="report_result_text",
        widget_key="report_result_view",
    )
    _render_logs("report_logs")


def _apply_dashboard_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1180px;
            padding-top: 1.6rem;
            padding-bottom: 2rem;
        }
        h1 {
            font-size: 1.65rem !important;
            font-weight: 650 !important;
            letter-spacing: 0 !important;
            margin-bottom: 0.35rem !important;
        }
        h4 {
            font-size: 0.98rem !important;
            font-weight: 650 !important;
            letter-spacing: 0 !important;
            margin-top: 1.2rem !important;
        }
        div[data-testid="stTabs"] button {
            font-size: 0.95rem;
            letter-spacing: 0;
        }
        div[data-testid="stTextArea"] textarea {
            font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            line-height: 1.55;
        }
        div[data-testid="stTextArea"] textarea:disabled {
            background: #f8fafc;
            color: #1f2937;
            -webkit-text-fill-color: #1f2937;
            opacity: 1;
        }
        div.stButton > button,
        div.stDownloadButton > button {
            border-radius: 6px;
            min-height: 2.55rem;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


try:
    APP_CONFIG = init_app()
except Exception as e:
    st.error(f"应用初始化失败: {e}")
    st.stop()

_init_session_state()
_apply_dashboard_style()

st.title("良率日报工作台")

download_tab, analysis_tab, report_tab = st.tabs(["报表下载", "数据分析", "日报生成"])

with download_tab:
    _render_download_tab()

with analysis_tab:
    _render_analysis_tab()

with report_tab:
    _render_report_tab()
