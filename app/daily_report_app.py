"""Standalone Streamlit UI for daily report generation."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from app.daily_report_service import (
    DEFAULT_REPORT_OUTPUT_DIR,
    DailyReportFormInput,
    DailyReportRunView,
    DownloadableReport,
    generate_daily_report,
    list_generated_reports,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def default_generator_root() -> Path:
    configured = os.getenv("DAILY_REPORT_GENERATOR_ROOT")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".agents" / "skills" / "daily-report-generator"


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def download_key(report: DownloadableReport, *, prefix: str, index: int) -> str:
    return f"{prefix}-{index}-{report.path.resolve()}"


def main() -> None:
    st.set_page_config(
        page_title="Excel日报生成",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _apply_styles()

    st.title("Excel日报生成")

    with st.sidebar:
        st.subheader("运行设置")
        generator_workspace_text = st.text_input("运行目录", value=str(REPO_ROOT))
        generator_root_text = st.text_input("Skill目录", value=str(default_generator_root()))
        output_dir_text = st.text_input("输出目录", value=str(DEFAULT_REPORT_OUTPUT_DIR))

    left, right = st.columns([0.46, 0.54], gap="large")

    with left:
        st.subheader("参数")
        with st.form("daily_report_form", clear_on_submit=False):
            report_date = st.date_input("报告日期", value=date.today())
            pin_runtime = st.checkbox("指定运行时间", value=False)
            generator_now = ""
            if pin_runtime:
                run_time = st.time_input("运行时间", value=datetime.now().time().replace(microsecond=0))
                generator_now = f"{report_date.isoformat()}T{run_time.isoformat()}"
            submitted = st.form_submit_button("生成日报", use_container_width=True)

        if submitted:
            _run_generation(
                report_date=report_date,
                generator_now=generator_now,
                generator_workspace_text=generator_workspace_text,
                generator_root_text=generator_root_text,
                output_dir_text=output_dir_text,
            )

    with right:
        st.subheader("状态")
        result = st.session_state.get("daily_report_last_result")
        if isinstance(result, DailyReportRunView):
            _render_result(result)
        else:
            st.info("等待生成")

        st.subheader("最近生成")
        reports = list_generated_reports(Path(output_dir_text), workspace=REPO_ROOT, limit=12)
        _render_downloads(reports, empty_message="暂无可下载文件", key_prefix="recent")


def _run_generation(
    *,
    report_date: date,
    generator_now: str,
    generator_workspace_text: str,
    generator_root_text: str,
    output_dir_text: str,
) -> None:
    generator_root = Path(generator_root_text).expanduser() if generator_root_text.strip() else None
    form = DailyReportFormInput(
        report_date=report_date.isoformat(),
        generator_workspace=Path(generator_workspace_text).expanduser(),
        generator_root=generator_root,
        output_dir=Path(output_dir_text).expanduser(),
        generator_now=generator_now or None,
    )
    try:
        with st.spinner("正在生成日报..."):
            result = generate_daily_report(form, workspace=REPO_ROOT)
    except Exception as exc:  # pragma: no cover - rendered through Streamlit runtime
        result = DailyReportRunView(
            success=False,
            summary="日报生成失败",
            error_message=f"{type(exc).__name__}: {exc}",
        )
    st.session_state["daily_report_last_result"] = result


def _render_result(result: DailyReportRunView) -> None:
    if result.success:
        st.success(result.summary or "日报生成完成")
    else:
        st.error(result.summary or "日报生成失败")

    if result.error_message:
        st.code(result.error_message, language="text")
    if result.output_file:
        st.write(f"输出文件：`{result.output_file}`")
    if result.workflow:
        st.write("流程：" + " → ".join(result.workflow))
    for warning in result.warnings:
        st.warning(warning)
    _render_downloads(
        result.downloads,
        empty_message="本次运行未返回可下载文件",
        key_prefix="result",
    )


def _render_downloads(
    reports: list[DownloadableReport],
    *,
    empty_message: str,
    key_prefix: str,
) -> None:
    if not reports:
        st.caption(empty_message)
        return

    for index, report in enumerate(reports):
        columns = st.columns([0.66, 0.18, 0.16], vertical_alignment="center")
        columns[0].write(report.label)
        columns[1].caption(format_size(report.size_bytes))
        try:
            data = report.path.read_bytes()
        except OSError as exc:
            columns[2].error(str(exc))
            continue
        columns[2].download_button(
            "下载",
            data=data,
            file_name=report.path.name,
            mime=EXCEL_MIME,
            key=download_key(report, prefix=key_prefix, index=index),
            use_container_width=True,
        )


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            max-width: 1180px;
        }
        div[data-testid="stForm"] {
            border: 1px solid rgba(49, 51, 63, 0.15);
            border-radius: 8px;
            padding: 1rem;
        }
        div[data-testid="stHorizontalBlock"] button {
            min-height: 2.4rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
