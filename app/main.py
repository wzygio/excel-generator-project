"""Streamlit UI entrypoint for the yield report workspace."""

from __future__ import annotations

import logging
from datetime import datetime
from hashlib import md5
from pathlib import Path
from typing import Any

import streamlit as st

from app.utils.app_setup import initialize_app, print_startup_banner
from yield_report.agent.spec_model import RunContext, SkillResult
from yield_report.skills.daily_report import tool as daily_report_tool
from yield_report.skills.daily_report.models import DailyReportRequest
from yield_report.skills.data_analysis import tool as data_analysis_tool
from yield_report.skills.data_analysis.models import DataAnalysisRequest
from yield_report.skills.report_download import tool as report_download_tool
from yield_report.skills.report_download.models import ReportDownloadRequest

logger = logging.getLogger(__name__)
RESULT_AREA_HEIGHT = 320
REPORT_OUTPUT_NAME = "daily_report_output.xlsx"


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


def _init_session_state() -> None:
    defaults: dict[str, Any] = {
        "download_result_text": "",
        "analysis_result_text": "",
        "analysis_step_text": "",
        "analysis_memory_record_id": "",
        "analysis_feedback_text": "",
        "report_result_text": "",
        "report_artifact_paths": {},
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


def _new_run_context() -> RunContext:
    return RunContext(
        run_id=datetime.now().strftime("ui-%Y%m%d-%H%M%S"),
        workspace=Path.cwd(),
        output_dir=Path(APP_CONFIG.paths.output_dir),
    )


def _format_download_result(result: SkillResult) -> str:
    request = result.data.get("parsed_request") or {}
    files = result.data.get("files") or []
    lines = [
        result.summary,
        "",
        "解析结果",
        f"- 报表类型: {request.get('report_type') or '未指定'}",
        f"- 开始日期: {request.get('start_date') or '未指定'}",
        f"- 结束日期: {request.get('end_date') or '未指定'}",
        f"- 产品型号: {_join_values(request.get('product_models'))}",
        f"- 用户意图: {request.get('user_intent') or '未指定'}",
    ]
    if request.get("uncertainty_notes"):
        lines.append(f"- 不确定信息: {request['uncertainty_notes']}")

    lines.extend(["", "下载结果"])
    for item in files:
        status = "成功" if item.get("success") else "失败"
        detail = item.get("file_path") if item.get("success") else item.get("error_message")
        lines.append(f"- {status}: {item.get('file_description') or '未命名文件'} -> {detail}")

    return "\n".join(lines)


def _format_analysis_result(result: SkillResult) -> str:
    request = result.data.get("parsed_request") or {}
    lines: list[str] = []

    if request:
        lines.extend(
            [
                "解析结果",
                f"- 数据源类型: {request.get('source_file_type') or '未指定'}",
                f"- 产品型号: {_join_values(request.get('product_models'))}",
                f"- 时间范围: {request.get('start_date') or '未指定'} ~ {request.get('end_date') or '未指定'}",
                f"- 目标指标: {_join_values(request.get('target_metrics'))}",
                f"- 分析逻辑: {request.get('analysis_logic') or '未指定'}",
                f"- 用户意图: {request.get('user_intent') or '未指定'}",
            ]
        )
        if request.get("uncertainty_notes"):
            lines.append(f"- 不确定信息: {request['uncertainty_notes']}")

    lines.extend(
        [
            "",
            "执行结果",
            f"- 状态: {'成功' if result.success else '失败'}",
            f"- 策略: {result.data.get('strategy_used') or 'N/A'}",
            f"- 数据文件: {result.data.get('source_file_path') or 'N/A'}",
            f"- Memory记录: {result.data.get('memory_record_id') or '未生成'}",
            "",
            "分析结论",
            result.data.get("result_text", "") if result.success else result.error.message if result.error else "",
        ]
    )
    return "\n".join(lines)


def _format_analysis_steps(result: SkillResult) -> str:
    steps = result.data.get("workflow_steps") or []
    if not steps:
        return "暂无步骤信息"

    lines: list[str] = []
    for index, step in enumerate(steps, start=1):
        status = {
            "success": "成功",
            "warning": "警告",
            "failed": "失败",
        }.get(step.get("status"), step.get("status"))
        lines.append(f"{index}. {step.get('name')} [{status}]")
        lines.append(f"   {step.get('detail')}")
    return "\n".join(lines)


def _format_report_result(result: SkillResult) -> str:
    products = result.data.get("products") or []
    source_files = result.data.get("source_files") or {}
    artifacts = result.artifacts or []
    lines = [
        result.summary,
        "",
        "执行结果",
        f"- 状态: {'成功' if result.success else '失败'}",
        f"- 日报日期: {result.data.get('report_date') or 'N/A'}",
        f"- 当日过货产品数: {len(products)}",
        "",
        "源文件",
    ]
    if source_files:
        for alias, path in source_files.items():
            lines.append(f"- {alias}: {path}")
    else:
        lines.append("- 未记录")

    lines.extend(["", "产物"])
    if artifacts:
        for artifact in artifacts:
            lines.append(f"- {artifact.kind}: {artifact.path}")
    else:
        lines.append("- 未生成")

    warnings = result.warnings or []
    if warnings:
        lines.extend(["", "Warnings"])
        lines.extend(f"- {warning}" for warning in warnings)

    return "\n".join(lines)


def _join_values(values: Any) -> str:
    if not values:
        return "未指定"
    if isinstance(values, list):
        return ", ".join(str(item) for item in values) if values else "未指定"
    return str(values)


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
                result = report_download_tool.run(
                    ReportDownloadRequest(user_query=query.strip()),
                    _new_run_context(),
                )
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
    st.markdown("#### 数据分析")
    left_col, right_col = st.columns([1.15, 0.85], gap="large")

    with left_col:
        st.caption("输入自然语言需求，系统会依次完成需求解析、文件扫描/下载、解密、Schema提取和分析执行。")
        query = st.text_area(
            "数据分析需求",
            key="analysis_query",
            height=120,
            placeholder="请分析M678近一周的日度CT良率变化趋势",
        )
        run_clicked = st.button("执行数据分析", type="primary", use_container_width=True)

    with right_col:
        with st.container(border=True):
            st.markdown("##### 当前链路")
            st.caption("模块二 Task2 验证路径")
            st.markdown(
                "- 需求解析\n"
                "- Agent-Memory 匹配\n"
                "- 本地文件扫描/缺失下载\n"
                "- 解密优先读取\n"
                "- CT良率趋势分析"
            )

    if run_clicked:
        if not query.strip():
            st.session_state.analysis_result_text = "请输入数据分析需求。"
            st.session_state.analysis_step_text = ""
            st.session_state.analysis_memory_record_id = ""
            _append_log("analysis_logs", "需求为空，未执行。", "WARN")
        else:
            _append_log("analysis_logs", f"开始处理需求: {query.strip()}")
            try:
                result = data_analysis_tool.run(
                    DataAnalysisRequest(question=query.strip()),
                    _new_run_context(),
                )
                st.session_state.analysis_result_text = _format_analysis_result(result)
                st.session_state.analysis_step_text = _format_analysis_steps(result)
                st.session_state.analysis_memory_record_id = (
                    result.data.get("memory_record_id") or ""
                )
                st.session_state.analysis_feedback_text = ""
                _append_log("analysis_logs", result.summary)
            except Exception as exc:
                logger.exception("数据分析流程失败")
                st.session_state.analysis_result_text = f"数据分析失败: {exc}"
                st.session_state.analysis_step_text = ""
                st.session_state.analysis_memory_record_id = ""
                _append_log("analysis_logs", f"数据分析失败: {exc}", "ERROR")

    step_col, result_col = st.columns([0.9, 1.3], gap="large")
    with step_col:
        st.markdown("#### 执行步骤")
        _render_result_area(
            "数据分析步骤",
            source_key="analysis_step_text",
            widget_key="analysis_step_view",
            height=RESULT_AREA_HEIGHT,
        )

        record_id = st.session_state.get("analysis_memory_record_id", "")
        if record_id:
            st.markdown("#### Memory反馈")
            confirm_col, reject_col = st.columns(2)
            if confirm_col.button("确认记忆", use_container_width=True):
                try:
                    data_analysis_tool.confirm_memory(record_id)
                    st.session_state.analysis_feedback_text = f"已确认记忆: {record_id}"
                    _append_log("analysis_logs", st.session_state.analysis_feedback_text)
                except Exception as exc:
                    st.session_state.analysis_feedback_text = f"确认失败: {exc}"
                    _append_log("analysis_logs", st.session_state.analysis_feedback_text, "ERROR")
            if reject_col.button("拒绝记忆", use_container_width=True):
                try:
                    data_analysis_tool.reject_memory(record_id)
                    st.session_state.analysis_feedback_text = f"已拒绝记忆: {record_id}"
                    _append_log("analysis_logs", st.session_state.analysis_feedback_text)
                except Exception as exc:
                    st.session_state.analysis_feedback_text = f"拒绝失败: {exc}"
                    _append_log("analysis_logs", st.session_state.analysis_feedback_text, "ERROR")
            if st.session_state.analysis_feedback_text:
                st.info(st.session_state.analysis_feedback_text)

    with result_col:
        st.markdown("#### 结果")
        _render_result_area(
            "数据分析结果",
            source_key="analysis_result_text",
            widget_key="analysis_result_view",
            height=420,
        )
    _render_logs("analysis_logs")


def _render_report_tab() -> None:
    st.markdown("#### 一键生成日报")
    st.caption(
        "从 resources/spotfire.xlsx 识别当日过货产品，读取良率、目标和异常源表，生成 Excel 日报。"
    )

    left_col, right_col = st.columns([1.1, 0.9], gap="large")
    with left_col:
        request_text = st.text_area(
            "日报生成需求",
            key="report_query",
            height=120,
            placeholder="可选：填写备注。直接点击“一键生成日报”即可执行默认日报流程。",
        )
        run_clicked = st.button("一键生成日报", type="primary", use_container_width=True)

    with right_col:
        with st.container(border=True):
            st.markdown("##### 默认流程")
            st.markdown(
                "- 读取 `resources/spotfire.xlsx`\n"
                "- 提取当日过货产品\n"
                "- 执行 Gap / 趋势 / 异常分析\n"
                "- 输出 Excel + JSON + Markdown"
            )

    if run_clicked:
        _append_log("report_logs", f"收到日报生成需求: {request_text.strip() or '默认日报流程'}")
        try:
            result = daily_report_tool.run(
                DailyReportRequest(
                    output_name=REPORT_OUTPUT_NAME,
                    output_dir=Path(APP_CONFIG.paths.output_dir),
                    emit_intermediate_artifacts=True,
                ),
                _new_run_context(),
            )
            st.session_state.report_result_text = _format_report_result(result)
            st.session_state.report_artifact_paths = {
                artifact.kind: str(artifact.path)
                for artifact in result.artifacts
            }
            _append_log("report_logs", result.summary)
            if not result.success and result.error:
                _append_log("report_logs", result.error.message, "ERROR")
        except Exception as exc:
            logger.exception("日报生成流程失败")
            st.session_state.report_result_text = f"日报生成失败: {exc}"
            st.session_state.report_artifact_paths = {}
            _append_log("report_logs", f"日报生成失败: {exc}", "ERROR")

    st.markdown("#### 结果")
    artifact_paths = st.session_state.get("report_artifact_paths", {})
    excel_path_text = artifact_paths.get("excel")
    excel_path = Path(excel_path_text) if excel_path_text else None
    if excel_path is not None and excel_path.exists():
        with excel_path.open("rb") as file:
            st.download_button(
                "下载日报 Excel",
                data=file,
                file_name=APP_CONFIG.paths.output_file or excel_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    sidecar_cols = st.columns(2)
    for index, kind in enumerate(["json", "markdown"]):
        path_text = artifact_paths.get(kind)
        if not path_text:
            continue
        path = Path(path_text)
        if path.exists():
            with path.open("rb") as file:
                sidecar_cols[index].download_button(
                    f"下载{kind.upper()}",
                    data=file,
                    file_name=path.name,
                    mime="application/octet-stream",
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
