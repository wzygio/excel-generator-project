"""
app/main.py: Streamlit 前端入口

本模块是良率日报生成系统的用户界面，提供:
1. 报表下载区: 通过"一键自动下载"或自然语言查询获取源表文件
2. 数据上传与分析区: 支持上传 5 份源表数据并触发分析
3. 报告下载区: 下载生成的 Excel 报告

界面布局:
    ┌──────────────────────────────────────────┐
    │  良率日报生成系统 v0.1.0                  │
    ├──────────────────────────────────────────┤
    │  侧边栏: 环境状态 + 配置信息              │
    │  ┌────────────────────────────────────┐   │
    │  │  Tab1: 报表下载                    │   │
    │  │  ├── 一键自动下载按钮              │   │
    │  │  ├── 自然语言查询输入              │   │
    │  │  └── 文件列表                      │   │
    │  ├────────────────────────────────────┤   │
    │  │  Tab2: 数据上传与分析              │   │
    │  │  ├── 文件上传区 (5份源表)          │   │
    │  │  ├── 分析控制按钮                  │   │
    │  │  └── 结果预览                      │   │
    │  ├────────────────────────────────────┤   │
    │  │  Tab3: 报告下载                    │   │
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
from datetime import date, datetime
from pathlib import Path
import json
from typing import Optional

import streamlit as st

from app.utils.app_setup import (
    check_environment,
    initialize_app,
    print_startup_banner,
)
from app.utils.reloader import unload_all_controlled_modules
from yield_report.yield_report.application.orchestrator import (
    DataAcquisitionOrchestrator,
)
from yield_report.yield_report.core.query_parser import ReportType

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


@st.cache_resource
def init_orchestrator() -> DataAcquisitionOrchestrator:
    """初始化数据获取编排器（缓存，仅执行一次）。"""
    return DataAcquisitionOrchestrator()


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

# ---- 报表下载相关状态 ----
if "query_history" not in st.session_state:
    st.session_state.query_history: list[dict] = []

if "last_query_result" not in st.session_state:
    st.session_state.last_query_result = None

QUERY_HISTORY_FILE = Path("docs/query_history.json")

def _load_query_history() -> list[dict]:
    """从磁盘加载查询历史。"""
    if QUERY_HISTORY_FILE.exists():
        try:
            return json.loads(QUERY_HISTORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []

def _save_query_history(history: list[dict]) -> None:
    """保存查询历史到磁盘。"""
    QUERY_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUERY_HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

if "smart_query_history" not in st.session_state:
    st.session_state.smart_query_history = _load_query_history()

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
st.caption("支持一键自动下载或自然语言查询获取源表数据，通过 LLM 自动分析并生成标准化的 Excel 日报。")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📥 报表下载", "📤 数据上传与分析", "📥 报告下载", "💬 智能查询"]
)

# ============================================================
# Tab 1: 报表下载 (默认 Tab，支持一键下载 + 自然语言查询)
# ============================================================
with tab1:
    st.markdown("### 📥 报表下载")
    st.caption(
        "一键获取所有源表文件，或通过自然语言描述您需要的报表，系统将自动从 FineReport 或本地文件系统获取对应数据。"
    )

    # ========== 一键自动下载区 ==========
    st.markdown("#### ⚡ 快捷操作")

    col_auto, col_info = st.columns([2, 3])

    with col_auto:
        auto_download = st.button(
            "📥 一键下载所有报表",
            type="primary",
            use_container_width=True,
            help="自动下载全部 5 份源表文件：V3良率报表(月周天+批次)、CT异常管理表、良率目标拆解表、Gap分析模板",
        )

    with col_info:
        st.info(
            "点击后将自动从 FineReport 及本地文件系统获取当天所需的全部 5 份源表文件。"
        )

    # 执行一键下载
    if auto_download:
        orchestrator = init_orchestrator()
        with st.spinner("正在一键下载所有报表..."):
            try:
                result = orchestrator.process_user_query("下载今天所有需要的报表")
                st.session_state.last_query_result = result
                st.session_state.query_history.append({
                    "query": "一键下载所有报表",
                    "result": result,
                })
                if result.success:
                    st.success("✅ 一键下载完成！")
                else:
                    st.warning("⚠️ 部分文件下载失败，详情见下方结果。")
            except Exception as e:
                st.error(f"❌ 下载过程中发生错误: {e}")
                logger.exception("一键下载失败")

    st.divider()

    # ========== 自然语言查询区 ==========
    st.markdown("#### 💬 自然语言查询")
    st.caption("如果快捷操作不满足需求，可以输入更具体的查询条件。")

    # 示例提示
    with st.expander("💡 查询示例（点击展开）", expanded=False):
        st.markdown("""
        您可以尝试以下查询语句：

        | 查询目的 | 示例语句 |
        |----------|----------|
        | 下载月周天报表 | "帮我下载今天的V3良率报表" |
        | 下载批次报表 | "下载最近三个月的批次良率数据" |
        | 下载批次报表含型号 | "下载指定产品型号的批次良率数据" |
        | 获取本地文件 | "帮我获取CT异常管理表" |
        | 获取所有文件 | "帮我下载今天所有需要的报表" |
        | 指定日期 | "下载2026年5月10日的良率报表" |
        """)

    # 对话输入区
    col_input, col_btn = st.columns([5, 1])

    with col_input:
        user_query = st.text_input(
            "自然语言查询",
            placeholder="例如: 帮我下载今天的V3良率报表",
            label_visibility="collapsed",
        )

    with col_btn:
        submitted = st.button("🚀 执行查询", type="secondary", use_container_width=True)

    # 执行查询
    if submitted and user_query:
        with st.chat_message("user"):
            st.markdown(user_query)

        try:
            orchestrator = init_orchestrator()
            with st.spinner("正在解析查询并获取数据..."):
                result = orchestrator.process_user_query(user_query)

            st.session_state.last_query_result = result
            st.session_state.query_history.append({
                "query": user_query,
                "result": result,
            })

        except Exception as e:
            st.error(f"❌ 处理查询时发生错误: {e}")
            logger.exception("自然语言查询处理失败")

    elif submitted and not user_query:
        st.warning("请输入查询语句。")

    # ========== 结果显示区 ==========
    last_result = st.session_state.get("last_query_result")
    if last_result:
        st.divider()
        st.markdown("#### 📋 查询解析结果")

        # 显示解析参数
        req = last_result.parsed_request
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**报表类型**: {req.report_type.value if req.report_type else '全部'}")
            st.markdown(f"**开始日期**: {req.start_date or '自动'}")
        with col2:
            st.markdown(f"**结束日期**: {req.end_date or '自动'}")
            st.markdown(
                f"**产品型号**: "
                f"{', '.join(req.product_models) if req.product_models else '全部'}"
            )

        if req.user_intent:
            st.info(f"📝 意图识别: {req.user_intent}")

        if req.uncertainty_notes:
            st.warning(f"⚠️ 不确定信息: {req.uncertainty_notes}")

        # 显示执行结果
        st.divider()
        st.markdown(f"#### 📁 执行结果: {last_result.summary}")

        for res in last_result.results:
            if res.success:
                st.success(
                    f"✅ **{res.file_description}** → `{res.file_path}`"
                )
            else:
                st.error(
                    f"❌ **{res.file_description}** → {res.error_message}"
                )

        # 显示 resources/ 目录文件列表
        st.divider()
        st.markdown("#### 📂 resources/ 目录当前文件")

        resources_dir = Path(APP_CONFIG.paths.resources_dir)
        if resources_dir.exists():
            files = [
                f for f in resources_dir.iterdir()
                if f.is_file() and f.suffix in (".xlsx", ".xls", ".csv")
            ]
            if files:
                for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True):
                    mtime = f.stat().st_mtime
                    mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    st.text(f"📄 {f.name}  ({f.stat().st_size / 1024:.1f} KB, {mtime_str})")
            else:
                st.info("resources/ 目录下暂无 Excel 文件。")
        else:
            st.info("resources/ 目录不存在。")

    # ---- 查询历史 ----
    if st.session_state.query_history:
        st.divider()
        st.markdown("#### 📜 查询历史")

        for i, entry in enumerate(reversed(st.session_state.query_history[-5:])):
            with st.container():
                col_q, col_r = st.columns([1, 3])
                with col_q:
                    st.caption(f"#{len(st.session_state.query_history) - i}")
                with col_r:
                    status = "✅" if entry["result"].success else "❌"
                    st.markdown(f"{status} {entry['query']}")
                st.divider()

# ============================================================
# Tab 2: 数据上传与分析
# ============================================================
with tab2:
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
# Tab 3: 报告下载
# ============================================================
with tab3:
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
# Tab 4: 智能查询
# ============================================================
with tab4:
    from pathlib import Path
    from tests.analyze_yield.code_generator import CodeGenerator, extract_schema
    from tests.analyze_yield.code_executor import CodeExecutor

    st.markdown("### 💬 智能查询")
    st.caption(
        "输入自然语言查询需求，Claude 自动生成 pandas 代码对 Excel 文件进行分析。"
    )

    # ---- 文件选择区 ----
    st.markdown("#### 📂 选择数据文件")
    project_files_dir = Path("docs/project_files")
    if project_files_dir.exists():
        available_files = sorted(
            [f for f in project_files_dir.iterdir()
             if f.is_file() and f.suffix in (".xlsx", ".xls")],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        file_options = {f.name: f for f in available_files}
        selected_filename = st.selectbox(
            "选择要查询的 Excel 文件",
            options=list(file_options.keys()),
            help="列出 docs/project_files/ 下的所有 Excel 文件",
        )
        selected_file = file_options[selected_filename]

        # 显示 Schema 预览
        with st.expander("📋 文件 Schema 预览", expanded=False):
            try:
                schema = extract_schema(selected_file)
                st.code(schema, language="text")
            except Exception as e:
                st.warning(f"无法读取文件 schema: {e}")
    else:
        st.warning("docs/project_files/ 目录不存在。")
        selected_file = None

    # ---- 查询输入区 ----
    st.markdown("#### ✏️ 输入查询需求")

    with st.expander("💡 查询示例（点击展开）", expanded=False):
        st.markdown("""
        | 查询目的 | 示例语句 |
        |----------|----------|
        | 基本统计 | "统计良率的平均值、最大值和最小值" |
        | 筛选查询 | "搜出5月良率低于95%的数据" |
        | 分组聚合 | "按产品型号分组，计算各型号平均良率" |
        | 趋势分析 | "按日期排序，展示良率变化趋势" |
        """)

    # 代码预览 toggle
    preview_only = st.toggle(
        "🔍 仅生成代码，不执行",
        value=False,
        help="开启后只展示 Claude 生成的 pandas 代码，不会在本地执行。"
    )

    col_input, col_btn = st.columns([5, 1])
    with col_input:
        user_demand = st.text_input(
            "自然语言查询",
            placeholder="例如: 统计5月各型号良率的平均值和标准差",
            label_visibility="collapsed",
            key="smart_query_input",
        )
    with col_btn:
        btn_label = "🧠 生成代码" if preview_only else "🚀 执行查询"
        execute_btn = st.button(btn_label, type="primary", use_container_width=True)

    # ---- 执行查询 ----
    if execute_btn and user_demand and selected_file:
        with st.chat_message("user"):
            st.markdown(user_demand)

        try:
            # Step 1: 提取 schema
            with st.spinner("正在分析文件结构..."):
                schema = extract_schema(selected_file)
                abs_path = str(selected_file.resolve())

            # Step 2: Claude CLI 生成代码
            with st.spinner("Claude 正在生成分析代码..."):
                generator = CodeGenerator(claude_bin="claude")
                generated_code = generator.generate_code(schema, user_demand, abs_path)

            # Step 3: 显示生成的代码（始终展示）
            with st.expander("🔍 查看生成的代码", expanded=True):
                st.code(generated_code, language="python")

            if preview_only:
                st.info("代码预览模式 — 未执行。如需执行，请关闭上方 toggle 后重新点击按钮。")
                # 仅预览也记录历史
                st.session_state.smart_query_history.append({
                    "query": user_demand,
                    "file": selected_file.name,
                    "success": True,
                    "preview_only": True,
                    "code": generated_code,
                })
                _save_query_history(st.session_state.smart_query_history)
            else:
                # Step 4: 执行代码
                with st.spinner("正在执行分析..."):
                    executor = CodeExecutor()
                    result = executor.execute(generated_code)

                # Step 5: 显示结果
                st.divider()
                st.markdown("#### 📊 查询结果")

                if result.success:
                    if result.dataframes:
                        for i, df in enumerate(result.dataframes):
                            st.dataframe(df, use_container_width=True)
                    else:
                        st.code(result.stdout, language="text")
                else:
                    st.error(f"代码执行失败:\n```\n{result.error_message}\n```")
                    if result.stdout:
                        st.markdown("**部分输出:**")
                        st.code(result.stdout, language="text")

                # 记录查询历史并持久化
                st.session_state.smart_query_history.append({
                    "query": user_demand,
                    "file": selected_file.name,
                    "success": result.success,
                    "preview_only": False,
                    "error": result.error_message if not result.success else "",
                })
                _save_query_history(st.session_state.smart_query_history)

        except RuntimeError as e:
            st.error(f"Claude 代码生成失败: {e}")
        except Exception as e:
            st.error(f"查询执行失败: {e}")

    elif execute_btn and not user_demand:
        st.warning("请输入查询语句。")
    elif execute_btn and not selected_file:
        st.warning("请选择要查询的文件。")

    # ---- 查询历史 ----
    if st.session_state.smart_query_history:
        st.divider()
        st.markdown("#### 📜 查询历史")
        for i, entry in enumerate(reversed(st.session_state.smart_query_history[-10:])):
            with st.container():
                if entry.get("preview_only"):
                    status = "🔍"
                else:
                    status = "✅" if entry["success"] else "❌"
                st.markdown(
                    f"{status} **{entry['file']}** — {entry['query']}"
                )

# ============================================================
# 页脚
# ============================================================
st.divider()
st.caption(
    "良率日报生成系统 v0.1.0 | "
    "基于 DeepSeek / Gemini LLM | "
    "遵循 DDD + TDD 原则开发"
)
