# tests/test_excel_processor.py

#%%
import logging, json
import sys
from pathlib import Path

# 将项目根目录添加到Python路径
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

# --- 1. 从 src.config 导入所有需要的配置 ---
from src.excel_generator_project.config import CONFIG, TEMP_PATH, OUTPUT_PATH
from src.excel_generator_project.utils.utils import Utils
from excel_generator_project.core.data_processor import DataProcessor
from excel_generator_project.core.exception_processor import ExceptionProcessor
from excel_generator_project.core.font_processor import FontProcessor


if __name__ == '__main__':
    try:
        Utils.setup_test_environment("data_processor.log")
        logging.info("===== 开始执行 DataProcessor 自动化流程 =====")

        # 1. 初始化processor
        # processor = DataProcessor(CONFIG)
        # processor = ExceptionProcessor(CONFIG)
        processor = FontProcessor(TEMP_PATH, OUTPUT_PATH, CONFIG)

        # 2. 调用 run() 方法来执行所有在YAML中定义的任务
        data = processor.run()

        # 输出最新任务的结果
        logging.info(f"{json.dumps(data, ensure_ascii=False, indent=2)}")

        # 3. 任务完成后，显示人工验证提示
        Utils.manual_verification_prompt(str(OUTPUT_PATH))
        logging.info("自动化流程成功结束。")

    except Exception as e:
        logging.error(f"流程执行过程中发生未知异常: {e}", exc_info=True)
        print(f"\n❌ 流程执行过程中发生未知异常: {e}")

# %%
