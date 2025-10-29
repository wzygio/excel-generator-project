# ui/streamlit_app.py
import sys
from pathlib import Path
import datetime
import streamlit as st
import subprocess
import os
import time, logging, shutil
import tempfile # 导入tempfile模块

# --- 路径设置 ---
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from src.excel_generator_project.config import TEMPLATE_PATH, TEMP_PATH
from src.excel_generator_project.utils.utils import Utils

PYTHON_EXECUTABLE = sys.executable

# --- 辅助函数 (已重构) ---
def save_uploaded_file(uploaded_file, save_path: Path):
    """(已更新为先删除后保存的模式) 保存上传的文件到指定路径"""
    try:
        # --- 核心修改：在写入新文件前，先检查并删除已存在的旧文件 ---
        if save_path.exists():
            logging.info(f"检测到已存在的目标文件 '{save_path}'，正在删除...")
            save_path.unlink() # 使用 unlink 删除文件
            logging.info(f"旧文件已成功删除。")
        # --- 修改结束 ---

        # 将文件指针重置到开头
        uploaded_file.seek(0)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用 shutil.copyfileobj 进行流式复制
        with open(save_path, "wb") as f:
            shutil.copyfileobj(uploaded_file, f)
            
        logging.info(f"文件 '{uploaded_file.name}' 已成功保存到 '{save_path}'")
        return save_path
    except Exception as e:
        logging.error(f"保存上传文件时出错: {e}", exc_info=True)
        raise

def generate_dynamic_filename() -> str:
    """根据当前时间段，生成动态的默认输出文件名。"""
    now = datetime.datetime.now()
    date_str = now.strftime('%Y%m%d')
    current_hour = now.hour

    if 0 <= current_hour < 12:
        # 规则1: 0点到12点之前，不添加时刻
        return f"V3屏体良率日报-{date_str}.xlsx"
    elif 12 <= current_hour < 16:
        # 规则2: 12点到16点之前，固定为14:00 (注意使用全角冒号)
        return f"V3屏体良率日报-{date_str}-14：00.xlsx"
    else: # 16:00 - 23:59
        # 规则3: 16点及以后，固定为16:00 (注意使用全角冒号)
        return f"V3屏体良率日报-{date_str}-16：00.xlsx"

def run_subprocess(script_path: str, template_path: str, output_path: str):
    """(已重构) 一个通用的、用于执行后台脚本的函数，强制使用UTF-8编码。"""
    st.info(f"正在执行脚本: {Path(script_path).name}...")
    
    # --- 核心修改：在环境变量中增加 PYTHONUTF8=1 ---
    process_env = os.environ.copy()
    process_env["TEMPLATE_PATH"] = str(template_path)
    process_env["OUTPUT_PATH"] = str(output_path)
    process_env["PYTHONPATH"] = os.environ.get("PYTHONPATH", "") + os.pathsep + str(PROJECT_ROOT)
    process_env["PYTHONUTF8"] = "1" # 强制子进程使用UTF-8
    # --- 修改结束 ---

    return subprocess.run(
        [PYTHON_EXECUTABLE, script_path],
        env=process_env, # 使用我们构建的、包含了新环境变量的字典
        capture_output=True, # 使用 capture_output 更简洁
        text=True,
        encoding='utf-8' # 现在解码方式和子进程的输出编码保证一致
    )

# --- Streamlit UI 界面 ---
st.set_page_config(page_title="Excel日报生成器", layout="wide")
st.title("📊 Excel日报自动化生成工具")

# --- 状态管理初始化 ---
if 'step1_result' not in st.session_state:
    st.session_state.step1_result = None
if 'step2_result' not in st.session_state:
    st.session_state.step2_result = None
if 'final_file_content' not in st.session_state:
    st.session_state.final_file_content = None
    st.session_state.final_filename = None

# --- 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 全局配置")

    # --- 调用新的辅助函数来设置默认文件名 ---
    if 'output_filename' not in st.session_state:
        # 仅在会话状态中不存在时，调用函数生成一次默认值
        st.session_state.output_filename = generate_dynamic_filename() 
    # text_input 会使用会话状态中的值作为默认值，并允许用户修改
    st.session_state.output_filename = st.text_input(
        "最终输出文件名", 
        value=st.session_state.output_filename
    )

    st.divider()
    if st.button("🔄 Rerun", use_container_width=True):
        # 遍历并删除会话状态中的所有键，实现彻底重置
        for key in st.session_state.keys():
            del st.session_state[key]
        st.success("状态已清除！")
        time.sleep(1)
        st.rerun()

# --- 主界面：使用选项卡分离两个主要功能 ---
tab1, tab2 = st.tabs(["生成基础日报", "渲染日报样式"])

# ==========================================================
# 选项卡一：生成日报
# ==========================================================
with tab1:
    st.header("生成基础日报")
    st.info(f"请从报表中下载《V3屏体良率日报》，并在这里上传")
    
    uploaded_template_file = st.file_uploader("📥 上传日报模板文件", type=['xlsx'], key="initial_template_uploader")
    
    is_template_valid = False
    if uploaded_template_file:
        if uploaded_template_file.name.startswith(TEMPLATE_PATH.stem):
            is_template_valid = True
        else:
            st.error(f"❌ 文件名无效！请确保上传的文件以'{TEMPLATE_PATH.stem}'开头。")
            is_template_valid = False
    else:
        is_template_valid = True

    if st.button("🎨 生成日报", type="primary", use_container_width=True, key="gen_base_report_btn", disabled=not is_template_valid):
        template_to_use = TEMPLATE_PATH
        if uploaded_template_file:
            try:
                save_uploaded_file(uploaded_template_file, TEMPLATE_PATH)
                template_to_use = TEMPLATE_PATH
            except Exception as e:
                st.error(f"更新默认模板时发生错误: {e}")
                st.stop()

        with st.spinner("正在运行数据处理模块..."):
            # --- 核心修改：移除 tempfile，直接写入到持久化的 TEMP_PATH ---
            result = run_subprocess(
                script_path='content_generator.py',
                template_path=str(template_to_use),
                output_path=str(TEMP_PATH)
            )
            st.session_state.step1_result = result
        st.rerun()

    # --- 渲染逻辑 ---
    result = st.session_state.get('step1_result')
    if result:
        # --- 核心修改：判断条件改回检查磁盘上的 TEMP_PATH 文件是否存在 ---
        if result.returncode == 0 and TEMP_PATH.exists():
            st.subheader("✅ 日报已生成！")

            with st.container(border=True):
                st.markdown("#### 下载日报")
                # --- 核心修改：直接从 TEMP_PATH 读取文件提供下载 ---
                with open(TEMP_PATH, "rb") as file:
                    st.download_button(
                        label="📥 点击下载日报",
                        data=file,
                        file_name=TEMP_PATH.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            
            with st.container(border=True):
                st.warning("如需渲染样式，请打开日报并保存，并在下一步上传")
        else:
            st.error("日报生成失败，请检查下方日志。")
        
        st.divider()
        with st.expander("查看后台执行日志", expanded=False):
            st.code(f"--- stdout ---\n{result.stdout}\n\n--- stderr ---\n{result.stderr}", language="text")
# ==========================================================
# 选项卡二：应用最终样式
# ==========================================================
with tab2:
    st.header("渲染日报样式")
    st.info("请在这里上传上一步生成的日报文件（请务必手动打开并保存一次），也可以上传自己修改好的日报文件")

    uploaded_intermediate_file = st.file_uploader("📥 上传日报文件", type=['xlsx'], key="intermediate_uploader")
    
    # --- 核心修改：增加即时文件名验证 ---
    is_intermediate_valid = False
    if uploaded_intermediate_file:
        # 验证上传的文件名是否以中间文件的核心名称开头
        if uploaded_intermediate_file.name.startswith(TEMP_PATH.stem):
            is_intermediate_valid = True
        else:
            st.error(f"❌ 文件名无效！请确保上传的文件以'{TEMP_PATH.stem}'开头。")
            is_intermediate_valid = False

    if uploaded_intermediate_file and is_intermediate_valid:
        if st.button("🎨 生成日报", type="primary", use_container_width=True, key="gen_final_report_btn"):
            # 同样使用临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                saved_intermediate_path = save_uploaded_file(
                    uploaded_intermediate_file,
                    temp_dir_path / uploaded_intermediate_file.name
                )
                
                final_output_path = temp_dir_path / st.session_state.output_filename

                with st.spinner("正在运行样式处理模块..."):
                    result = run_subprocess(
                        script_path='run_style_postprocess.py',
                        template_path=str(saved_intermediate_path),
                        output_path=str(final_output_path)
                    )
                
                if result.returncode == 0 and final_output_path.exists():
                    st.session_state.final_file_content = final_output_path.read_bytes()
                    st.session_state.final_filename = final_output_path.name

                st.session_state.step2_result = result
            st.rerun()
    elif uploaded_intermediate_file and not is_intermediate_valid:
        # 在按钮下方显示一条持久的警告，如果文件名无效
        st.warning("请上传一个文件名有效的文件以继续。")
    else:
        st.info("请先上传一个日报文件以继续。")
            
    # --- 根据会话状态来渲染结果UI ---
    result = st.session_state.get('step2_result')
    if result:
        if result.returncode == 0 and st.session_state.final_file_content:
            st.subheader(" 日报已生成！")
            st.download_button(
                label="🏆 点击下载日报",
                data=st.session_state.final_file_content,
                file_name=st.session_state.final_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
        else:
            st.error("最终样式应用失败，请检查下方日志。")
        
        # 将日志窗口移到最后，并默认折叠
        st.divider()
        with st.expander("查看后台执行日志", expanded=False):
            st.code(f"--- stdout ---\n{result.stdout}\n\n--- stderr ---\n{result.stderr}", language="text")
