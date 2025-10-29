# run_style_postprocess.py

import logging
import sys
import os
from pathlib import Path

# --- 路径设置 ---
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from src.excel_generator_project.config import CONFIG
from src.excel_generator_project.utils.utils import Utils
from excel_generator_project.core.font_processor import FontProcessor

def style_postprocess_flow():
    """
    第二部分：对一个已存在的报告文件进行字体和样式的后期处理。
    """
    Utils.setup_test_environment("style_postprocess.log")
    logging.info("===== [阶段二] 开始进行后期样式处理 =====")
    
    # 1. 从环境变量中读取UI传递过来的动态路径
    temp_path_str = os.getenv("TEMPLATE_PATH") # 此时的模板是上一阶段的输出
    output_path_str = os.getenv("OUTPUT_PATH")

    if not temp_path_str or not output_path_str:
        logging.error("错误：环境变量 TEMPLATE_PATH 或 OUTPUT_PATH 未设置。")
        sys.exit(1)

    temp_path = Path(temp_path_str)
    output_path = Path(output_path_str)
    logging.info(f"  输入文件: {temp_path.name}")
    logging.info(f"  最终输出路径: {output_path.name}")

    # 2. 运行字体处理器，进行富文本注入
    logging.info("  正在执行 FontProcessor 进行富文本注入...")
    font_processor = FontProcessor(
        template_path=temp_path,
        output_path=output_path,
        config=CONFIG
    )
    font_processor.run()

    # # 3. 运行最终的对齐样式修正工具
    # logging.info("  正在应用最终的单元格对齐样式...")
    # Utils.apply_alignment_styles(
    #     output_path=output_path,
    #     jobs_config=CONFIG.get('font_processing_jobs', [])
    # )

    logging.info(f"===== [阶段二] 后期样式处理完成: {output_path.name} =====")


if __name__ == '__main__':
    try:
        style_postprocess_flow()
    except Exception as e:
        logging.error(f"流程[阶段二]发生未知异常: {e}", exc_info=True)
        sys.exit(1)