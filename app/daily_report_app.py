"""Standalone Streamlit UI for daily report generation."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from app.daily_report_service import (
    DailyReportFormInput,
    DailyReportRunView,
    DownloadableReport,
    default_report_output_dir,
    generate_daily_report,
    list_generated_reports,
)
from yield_report.shared_kernel.config import ConfigLoader

REPO_ROOT = Path(__file__).resolve().parents[1]
EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def default_generator_root() -> Path:
    settings = ConfigLoader().get().agent.daily_report
    env_name = settings.generator_root_env.strip()
    configured = os.getenv(env_name) if env_name else None
    if configured:
        return Path(configured).expanduser()
    if not settings.generator_root.strip():
        raise ValueError("agent.daily_report.generator_root is not configured")
    return Path(settings.generator_root).expanduser()


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
        generator_workspace_text = st.text_input("兼容运行目录（可选）", value="")
        generator_root_text = st.text_input("Skill目录", value=str(default_generator_root()))
        output_dir_text = st.text_input("输出目录", value=str(default_report_output_dir()))

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
            submitted = st.form_submit_button("生成日报", width="stretch")

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

    reports = list_generated_reports(Path(output_dir_text), workspace=REPO_ROOT, limit=12)
    warnings = result.warnings if isinstance(result, DailyReportRunView) else []
    errors = (
        [result.error_message]
        if isinstance(result, DailyReportRunView) and result.error_message
        else []
    )
    _render_footer_sections(reports=reports, warnings=warnings, errors=errors)


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
        generator_workspace=(
            Path(generator_workspace_text).expanduser()
            if generator_workspace_text.strip()
            else None
        ),
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
    elif result.error_message:
        st.warning("日报生成失败，请展开下方 Warning / Error 查看详细信息")
    else:
        st.warning(result.summary or "日报生成失败")
    if result.output_file:
        st.write(f"输出文件：`{result.output_file}`")
    _render_downloads(
        result.downloads[:1],
        empty_message="本次运行未返回可下载文件",
        key_prefix="result",
    )


def _render_footer_sections(
    *,
    reports: list[DownloadableReport],
    warnings: list[str],
    errors: list[str] | None = None,
) -> None:
    with st.expander(f"历史文件（{len(reports)}）", expanded=False):
        _render_downloads(
            reports,
            empty_message="暂无可下载文件",
            key_prefix="recent",
        )

    errors = errors or []
    total_messages = len(warnings) + len(errors)
    with st.expander(f"Warning / Error（{total_messages}）", expanded=False):
        if not warnings and not errors:
            st.caption("暂无 Warning / Error")
            return
        for error in errors:
            st.error(error)
        for warning in warnings:
            st.warning(warning)


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
            width="stretch",
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
