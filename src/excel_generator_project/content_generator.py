#%%
# run_main_report.py
import logging
import sys
import os
from pathlib import Path

# --- 路径设置，确保可以导入src下的模块 ---
project_root = Path(__file__).parent.parent.parent.resolve()
src_root = project_root / 'src'
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from excel_generator_project.config import CONFIG, TEMPLATE_PATH, TEMP_PATH
from excel_generator_project.utils.utils import Utils
from excel_generator_project.core.data_processor import DataProcessor
from excel_generator_project.core.exception_processor import ExceptionProcessor
from excel_generator_project.services.report_generator import ReportGenerator

def main_report_flow():
    """
    第一部分：执行数据处理，并生成包含所有数据的中间报告文件。
    """
    Utils.setup_test_environment("main_report.log")
    logging.info("===== [阶段一] 开始生成基础数据报告 =====")

    # 1. 从环境变量中读取UI传递过来的动态路径
    template_path_str = os.getenv("TEMPLATE_PATH",str(TEMPLATE_PATH))
    temp_path_str = os.getenv("OUTPUT_PATH", str(TEMP_PATH))

    if not template_path_str or not temp_path_str:
        logging.error("错误：环境变量 TEMPLATE_PATH 或 OUTPUT_PATH 未设置。")
        sys.exit(1) # 以错误码退出，方便UI捕获

    template_path = Path(template_path_str)
    temp_path = Path(temp_path_str)
    logging.info(f"  使用模板: {template_path.name}")
    logging.info(f"  中间输出路径: {temp_path.name}")

    # 2. 依次运行所有数据处理器
    logging.info("  正在运行 ExceptionProcessor...") 
    exception_processor = ExceptionProcessor(CONFIG)
    exception_results = exception_processor.run()

    logging.info("  正在运行 DataProcessor...")
    # 假设DataProcessor也只需要config进行初始化
    data_processor = DataProcessor(CONFIG, exception_results) 
    data_results = data_processor.run()
    
    # 3. 准备生成器的配置，注入处理器返回的数据
    generator_config = CONFIG.copy()
    generator_config['EXTERNAL_DATA'] = {
        'exceptions_data': exception_results,
        'yield_data': data_results
    }

    # 4. 运行报告生成器，生成中间文件
    logging.info(f"  正在调用 ReportGenerator 生成中间报告...")
    report_generator = ReportGenerator(
        template_path=template_path,
        output_path=temp_path,
        config=generator_config
    )
    report_generator.run()

    logging.info(f"===== [阶段一] 基础数据报告生成完毕: {temp_path.name} =====")


if __name__ == '__main__':
    try:
        main_report_flow()
    except Exception as e:
        logging.error(f"流程[阶段一]发生未知异常: {e}", exc_info=True)
        sys.exit(1)
# %%
