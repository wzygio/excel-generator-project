"""
app/main.py: Streamlit 前端入口

本模块是良率日报生成系统的用户界面，提供:
1. 文件上传区: 支持上传 5 份源表数据
2. 分析控制区: 触发 Gap 分析、异常分析、趋势分析
3. 结果预览区: 展示分析结果摘要
4. 报告下载区: 下载生成的 Excel 报告

界面布局:
    ┌──────────────────────────────────────────┐
    │  良率日报生成系统 v0.1.0                  │
    ├──────────────────────────────────────────┤
    │  侧边栏: 环境状态 + 配置信息              │
    │  ┌────────────────────────────────────┐   │
    │  │  Tab1: 数据上传与分析              │   │
    │  │  ├── 文件上传区 (5份源表)          │   │
    │  │  ├── 分析控制按钮                  │   │
    │  │  └── 结果预览                      │   │
    │  ├────────────────────────────────────┤   │
    │  │  Tab2: 报告下载                    │   │
    │  │  └── 下载生成的 Excel 文件         │   │
    │  └────────────────────────────────────┘   │
    └──────────────────────────────────────────┘

使用方式:
    streamlit run app/main.py
    或
    uv run streamlit run app/main.py
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import streamlit as st

from app.utils.app_setup import (
    check_environment,
    initialize_app,
    print_startup_banner,
)
from app.utils.reloader import unload_all_controlled_modules

logger = logging.getLogger(__name__)

# ============================================================
# 页面配置 (必须在第一个 streamlit 命令之前)
# ============================================================
st.set_page_config(
    page_title="良率日报生成系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 应用初始化 (只在首次运行时执行)
# ============================================================
@st.cache_resource
def init_app():
    """初始化应用（缓存，仅执行一次）。"""
    config = initialize_app()
    print_startup_banner(config)
    return config


try:
    APP_CONFIG = init_app()
except Exception as e:
    st.error(f"应用初始化失败: {e}")
    st.stop()

# ============================================================
# 会话状态初始化
# ============================================================
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files: dict[str, Optional[bytes]] = {
        "daily_yield": None,      # V3良率及不良率By月周天汇总报表
        "batch_yield": None,      # V3良率及不良率By批次汇总报表
        "ct_exception": None,     # CT异常管理表
        "target_decomposition": None,  # 良率目标拆解表
        "gap_template": None,     # 日良率Gap分析模板
    }

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results: dict = {}

if "report_ready" not in st.session_state:
    st.session_state.report_ready = False

# ============================================================
# 侧边栏
# ============================================================
with st.sidebar:
    st.image("https://via.placeholder.com/200x80?text=良率日报", width=200)
    st.markdown(f"### {APP_CONFIG.app_name}")
    st.caption(f"v{APP_CONFIG.version}")

    st.divider()
    st.markdown("#### 环境状态")

    env_checks = check_environment()
    status_color = (
        "🟢" if env_checks["dotenv_loaded"] else "🟡"
    )
    st.markdown(f"{status_color} .env 已加载: {env_checks['dotenv_loaded']}")

    if env_checks["deepseek_key_set"]:
        st.markdown("🟢 DeepSeek Key: 已配置")
    else:
        st.markdown("🔴 DeepSeek Key: 未配置")

    if env_checks["gemini_key_set"]:
        st.markdown("🟢 Gemini Key: 已配置")
    else:
        st.markdown("🔴 Gemini Key: 未配置")

    st.divider()
    st.markdown("#### LLM 供应商")
    st.caption(f"当前: {APP_CONFIG.llm.provider}")

    st.divider()
    st.markdown("#### 配置路径")
    st.caption(f"base_dir: {APP_CONFIG.paths.base_dir}")
    st.caption(f"log_dir: {APP_CONFIG.paths.log_dir}")
    st.caption(f"output_dir: {APP_CONFIG.paths.output_dir}")


# ============================================================
# 主界面
# ============================================================
st.title("📊 良率日报生成系统")
st.caption("上传源表数据，系统将通过 LLM 自动分析并生成标准化的 Excel 日报。")

tab1, tab2 = st.tabs(["📤 数据上传与分析", "📥 报告下载"])

# ============================================================
# Tab 1: 数据上传与分析
# ============================================================
with tab1:
    st.markdown("### 第一步：上传源表数据")
    st.caption("请上传以下 5 份源表文件（均为 .xlsx 格式）")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**良率数据**")
        daily_yield_file = st.file_uploader(
            "V3良率及不良率By月周天汇总报表",
            type=["xlsx", "xls"],
            key="daily_yield",
            help="用于 Gap 计算的日/周/月维度良率数据",
        )
        batch_yield_file = st.file_uploader(
            "V3良率及不良率By批次汇总报表",
            type=["xlsx", "xls"],
            key="batch_yield",
            help="判断最新产出率>30%的批次是否恶化",
        )
        ct_exception_file = st.file_uploader(
            "CT异常管理表",
            type=["xlsx", "xls"],
            key="ct_exception",
            help="搜索当日与已知异常",
        )

    with col2:
        st.markdown("**目标与模板**")
        target_file = st.file_uploader(
            "良率目标拆解表",
            type=["xlsx", "xls"],
            key="target_decomposition",
            help="获取基准良率目标",
        )
        gap_template_file = st.file_uploader(
            "日良率Gap分析模板",
            type=["xlsx", "xls"],
            key="gap_template",
            help="Excel 输出模板",
        )

    # 文件上传状态
    uploaded_count = sum(
        1 for f in [daily_yield_file, batch_yield_file, ct_exception_file,
                     target_file, gap_template_file]
        if f is not None
    )

    if uploaded_count > 0:
        st.success(f"已上传 {uploaded_count}/5 份文件")
    else:
        st.info("等待上传...")

    # ---- 文件保存与状态更新 ----
    if daily_yield_file:
        st.session_state.uploaded_files["daily_yield"] = daily_yield_file.getvalue()
    if batch_yield_file:
        st.session_state.uploaded_files["batch_yield"] = batch_yield_file.getvalue()
    if ct_exception_file:
        st.session_state.uploaded_files["ct_exception"] = ct_exception_file.getvalue()
    if target_file:
        st.session_state.uploaded_files["target_decomposition"] = target_file.getvalue()
    if gap_template_file:
        st.session_state.uploaded_files["gap_template"] = gap_template_file.getvalue()

    st.divider()
    st.markdown("### 第二步：运行分析")

    # 检查是否所有文件都已上传
    all_uploaded = all(v is not None for v in st.session_state.uploaded_files.values())

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        run_button = st.button(
            "🚀 运行全部分析",
            disabled=not all_uploaded,
            type="primary",
            use_container_width=True,
        )
    with col2:
        if st.button("🔄 重置上传", use_container_width=True):
            for key in st.session_state.uploaded_files:
                st.session_state.uploaded_files[key] = None
            st.session_state.analysis_results = {}
            st.session_state.report_ready = False
            st.rerun()

    if not all_uploaded:
        st.warning("请先上传全部 5 份源表文件后再运行分析。")

    if run_button:
        with st.spinner("正在运行全部分析模块..."):
            # ---- 此处预留分析模块的调用入口 ----
            # 分析完成后，会将结果写入 st.session_state.analysis_results
            # 并设置 st.session_state.report_ready = True

            # 模拟分析进度
            progress_bar = st.progress(0, text="开始分析...")
            
            # TODO: Step 1 - 数据提取
            progress_bar.progress(20, text="正在提取数据...")
            
            # TODO: Step 2 - Gap 分析 (LLM)
            progress_bar.progress(40, text="正在执行 Gap 分析...")
            
            # TODO: Step 3 - 异常分析 (LLM)
            progress_bar.progress(60, text="正在执行异常分析...")
            
            # TODO: Step 4 - 趋势分析 (LLM)
            progress_bar.progress(80, text="正在执行趋势分析...")
            
            # TODO: Step 5 - 报告生成
            progress_bar.progress(100, text="报告生成完成!")

            st.session_state.report_ready = True
            st.success("✅ 分析完成！请切换到「报告下载」标签页。")

    # ---- 结果预览 ----
    if st.session_state.analysis_results:
        st.divider()
        st.markdown("### 分析结果预览")
        with st.expander("查看详细结果"):
            st.json(st.session_state.analysis_results)

# ============================================================
# Tab 2: 报告下载
# ============================================================
with tab2:
    st.markdown("### 生成报告下载")

    if not st.session_state.report_ready:
        st.info("请先在「数据上传与分析」标签页中完成分析。")
    else:
        st.success("报告已生成，请点击下方按钮下载。")

        # TODO: 替换为实际的报告文件路径
        report_path = APP_CONFIG.paths.output_dir / APP_CONFIG.paths.output_file

        if Path(report_path).exists():
            with open(report_path, "rb") as f:
                st.download_button(
                    label="📥 下载 Excel 日报",
                    data=f,
                    file_name=APP_CONFIG.paths.output_file,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )
        else:
            st.warning("报告文件尚未生成。请完成分析流程。")

    st.divider()
    st.markdown("### 报告模块概览")
    st.markdown("""
    生成的 Excel 报告包含以下三大核心模块:

    | 模块 | 说明 |
    |------|------|
    | **【当日Gap解释】** | 日良率 Gap 分析 + 批次恶化/集中过货判定 |
    | **【当日异常】** | 当日新发现的异常（Top3 Code 高亮） |
    | **【已知异常】** | 影响当日良率的已有异常记录 |
    """)

# ============================================================
# 页脚
# ============================================================
st.divider()
st.caption(
    "良率日报生成系统 v0.1.0 | "
    "基于 DeepSeek / Gemini LLM | "
    "遵循 DDD + TDD 原则开发"
)
