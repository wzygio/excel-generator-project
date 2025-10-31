# src/processors/excel_processor.py
import re, os
import json
import logging
from pathlib import Path
import datetime
from datetime import datetime as dt

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter

from excel_generator_project.config import BASE_DIR, DATA_DIR
from excel_generator_project.utils.utils import Utils

class DataProcessor:
    """
    配置驱动的Excel报告处理器。
    """
    def __init__(self, config: dict):
        """
        (已更新) 初始化处理器。
        'output_path' 是指本次处理流程中使用的临时文件路径。
        """
        self.config = config
        self.excel_handler = None # 统一命名
        self.calculated_data = {}
        self.product_models = Utils.extract_product_models(config.get("model_definitions", "")) # 提取日报中产品型号
        
    def run(self):
        """
        主调度方法。
        它会先复制模板到输出路径，然后根据配置中的任务列表，依次执行所有任务。
        """
        logging.info(f"--- DataProcessor 开始运行 ---")

        # 调度并执行所有任务
        jobs = self.config.get('data_processing_jobs', []) # 注意，这里需要匹配您YAML中的键名
        logging.info(f"发现 {len(jobs)} 个待处理任务...")

        for i, job_config in enumerate(jobs, 1):
            job_type = job_config.get("job_type")
            logging.info(f"--> 开始执行任务 {i}/{len(jobs)}: 类型 = {job_type}")
    
            if job_type == "daily_yield_change":
                self._execute_daily_yield_change_job(job_config) # 当日修正良率变化：self.calculated_data['daily_yield_change']
            # elif job_type == "extract_bp_target": 
            #     self._execute_extract_bp_target_job(job_config) # BP良率目标：self.calculated_data['bp_target']
            elif job_type == "extract_tila_target": 
                self._execute_extract_tila_target_job(job_config) # 提拉良率目标：self.calculated_data['tila_target']
            elif job_type == "extract_monthly_yield_estimate": 
                # 月度良率预估：self.calculated_data['prod_target'] 和 self.calculated_data['estimated_yield']
                self._execute_extract_monthly_yield_estimate_job(job_config) 
            elif job_type == "extract_batch_info": 
                # 最新最优批次：self.calculated_data['newest_batch_info'] 和 self.calculated_data['best_batch_info']
                self._execute_extract_batch_info_job(job_config) 
            elif job_type == "extract_risk_items": 
                self._execute_extract_risk_items_job(job_config) # 风险品：self.calculated_data['risk_items']
            elif job_type == "prepare_summary_data":
                self._execute_prepare_summary_data(job_config)
            else:
                logging.warning(f"未知的任务类型 '{job_type}'，已跳过。")

        # 输出最新任务的结果
        logging.info(f"{json.dumps(self.calculated_data, ensure_ascii=False, indent=2)}")

        logging.info(f"--- DataProcessor 运行结束 ---")
        return self.calculated_data['summary_report_data']
    
    def _execute_prepare_summary_data(self, job_config: dict):
        """
        仅负责准备用于填充模板的数据，并将其存入 self.calculated_data。
        """
        logging.info("    开始执行“准备摘要数据”任务...")
        
        # 假设 __prepare_data_for_templating 是一个已存在的私有方法
        all_reports_data = self.__prepare_data_for_templating()
        
        if not all_reports_data:
            logging.warning("    没有可用于准备摘要的数据。")
            return
        
        # 将准备好的数据列表存入 self.calculated_data，供后续 Generator 使用
        self.calculated_data['summary_report_data'] = all_reports_data
        logging.info(f"    已成功为 {len(all_reports_data)} 个产品型号准备好摘要数据。")

    def __prepare_data_for_templating(self) -> list[dict]:
        """
        (新辅助方法) 将 self.calculated_data 中所有零散的数据，
        整合成一个可以直接用于填充模板的“数据包”列表。
        """
        all_reports_data = []
        num_models = len(self.product_models)

        # 从 self.calculated_data 中安全地获取数据
        dc = self.calculated_data
        daily_yield_list = dc.get('daily_yield_change', [])
        bp_target_list = dc.get('bp_target', [])
        tila_target_list = dc.get('tila_target', [])
        prod_yield_list = dc.get('production_yield_values', [])
        month_yield_list = dc.get('monthly_yield_values', [])
        newest_batch_map = dc.get('newest_batch_info', {})
        best_batch_map = dc.get('best_batch_info', {})
        risk_items_map = dc.get('risk_items', {})

        # 遍历每个产品型号，为其打包一份专属的数据字典
        for i, model in enumerate(self.product_models):
            # 处理 risk_items 的格式，将其从字典转换为多行字符串
            risk_items_for_model = risk_items_map.get(model, {})
            risk_items_str = "\n".join(risk_items_for_model.values()) if risk_items_for_model else "/"

            # 构建数据字典，key必须与模板中的占位符完全对应
            # 使用 try-except 或 get 方法来安全地获取数据，防止因某个数据缺失导致整个流程失败
            report_data = {
                'model_name': model, # 额外添加一个型号名称，便于日志记录
                'daily_yield_change': daily_yield_list[i] if i < len(daily_yield_list) else "N/A",
                'new_exceptions': "/", # 占位符，未来可扩展
                'known_exceptions': "/", # 占位符，未来可扩展
                'bp_target': bp_target_list[i] if i < len(bp_target_list) else "N/A",
                'tila_target': tila_target_list[i] if i < len(tila_target_list) else "N/A",
                'prod_target': prod_yield_list[i] if i < len(prod_yield_list) else "N/A",
                'estimated_yield': month_yield_list[i] if i < len(month_yield_list) else "N/A",
                'best_batch': best_batch_map.get(model, "/"),
                'latest_batch_info': newest_batch_map.get(model, "/"),
                'risk_items': risk_items_str,
                'unique_exceptions': "/", # 占位符，未来可扩展
                'array_opportunities': "/", # 占位符，未来可扩展
                'oled_opportunities': "/", # 占位符，未来可扩展
                'tp_opportunities': "/" # 占位符，未来可扩展
            }
            all_reports_data.append(report_data)

        return all_reports_data

    def _execute_daily_yield_change_job(self, job_config: dict):
        """
        执行“提取当日良率变化值”的任务。
        此方法根据精确的步长迭代逻辑，从源文件的文本段落中提取一个数字，
        并将其存入 self.calculated_data。
        """
        # --- 1. 解析并验证配置 ---
        source_path = Utils.get_safe_source_path(job_config)
        if not source_path or not source_path.is_file():
            logging.error(f"    未能获取有效的源文件路径，任务中止。")
            return

        sheet_name = job_config.get("sheet_name")
        pattern = job_config.get("pattern")
        sequence = job_config.get("cell_sequence", {})
        start_cell = sequence.get("start_cell")
        step = sequence.get("step")
        end_row = sequence.get("end_row")

        # 确保所有必需的配置项都存在且有效
        if not all([source_path.is_file(), sheet_name, pattern, start_cell, isinstance(step, int), isinstance(end_row, int)]):
            logging.error("任务 'daily_yield_change' 配置不完整、类型错误或源文件不存在。")
            return

        try:
            # --- 2. 加载源数据文件 ---
            source_wb = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
            if sheet_name not in source_wb.sheetnames:
                logging.error(f"工作表 '{sheet_name}' 在文件 '{source_path.name}' 中未找到。")
                return
            source_ws = source_wb[sheet_name]

            # --- 3. 实现您指定的步长迭代逻辑 ---
            # 从 'B4' 中解析出列 'B' 和起始行 4
            col_letter = ''.join(filter(str.isalpha, start_cell))
            current_row = int(''.join(filter(str.isdigit, start_cell)))

            extracted_list = []
            consecutive_none_count = 0 # 新增：初始化空值计数器
            logging.info(f"    开始在 {source_path.name}[{sheet_name}] 中按步长 {step} 搜索...")
            
            # 循环直到当前行超过结束行
            while current_row <= end_row:
                cell_address = f"{col_letter}{current_row}"
                cell_value = source_ws[cell_address].value
                
                # --- 新增：边界条件判断逻辑 ---
                if cell_value is None:
                    consecutive_none_count += 1
                else:
                    consecutive_none_count = 0
                
                if consecutive_none_count >= 2:
                    logging.info(f"    检测到连续两次空值，提取在第 {current_row} 行提前终止。")
                    break

                if isinstance(cell_value, str):
                    match = re.search(str(pattern), cell_value)
                    if match:
                        # 提取第一个捕获组的内容
                        extracted_value = match.group(1).strip()
                        logging.info(f"    在单元格 {cell_address} 中找到匹配项。提取值: {extracted_value}")
                        extracted_list.append(extracted_value)

                # 移动到下一个目标单元格
                current_row += step

            # --- 4. 存储提取结果 ---
            if extracted_list:
                self.calculated_data['daily_yield_change'] = extracted_list
                logging.info(f"    数据提取成功: daily_yield_change 已存为包含 {len(extracted_list)} 个值的列表。")
            else:
                logging.warning(f"    未能在指定的单元格序列中找到与模式 '{pattern}' 匹配的数据。")

        except Exception as e:
            logging.error(f"    处理任务 'daily_yield_change' 时发生意外错误: {e}", exc_info=True)


    def _execute_extract_bp_target_job(self, job_config: dict):
        """
        执行“提取BP良率目标”的任务。
        此方法会先动态查找起始行，然后按步长提取一系列数据。
        """
        # --- 1. 解析并验证配置 ---
        source_path = Utils.get_safe_source_path(job_config)
        if not source_path or not source_path.is_file():
            logging.error(f"    未能获取有效的源文件路径，任务中止。")
            return
        sheet_name = job_config.get("sheet_name")
        finder_config = job_config.get("start_row_finder", {})
        extraction_config = job_config.get("data_extraction", {})

        if not all([source_path.is_file(), sheet_name, finder_config, extraction_config]):
            logging.error("任务 'extract_bp_target' 配置不完整或源文件不存在。")
            return

        try:
            # --- 2. 加载源数据文件 ---
            source_wb = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
            if sheet_name not in source_wb.sheetnames:
                logging.error(f"工作表 '{sheet_name}' 在文件 '{source_path.name}' 中未找到。")
                return
            source_ws = source_wb[sheet_name]

            # --- 3. 动态查找起始行 ---
            search_col = finder_config.get('search_column')
            search_val = finder_config.get('search_value')
            max_row = finder_config.get('max_search_row', 200) # 提供一个默认值
            
            start_row = None
            logging.info(f"    在 {search_col} 列中搜索关键字 '{search_val}'...")
            for row in range(1, max_row + 1):
                cell_value = source_ws[f"{search_col}{row}"].value
                # 检查单元格内容是否为字符串，以及是否包含关键字
                if isinstance(cell_value, str) and search_val in cell_value:
                    start_row = row
                    logging.info(f"    找到起始行: {start_row}")
                    break
            
            if start_row is None:
                logging.warning(f"    未能在 {max_row} 行内找到包含 '{search_val}' 的单元格，任务中止。")
                return

            # --- 4. 按步长提取数据序列 (已更新终止逻辑) ---
            data_col = extraction_config.get('data_column')
            step = extraction_config.get('step')
            end_row = extraction_config.get('end_row')

            current_row = start_row
            extracted_list = []
            consecutive_none_count = 0 # 初始化None值计数器
            logging.info(f"    从 {data_col} 列的第 {current_row} 行开始，按步长 {step} 提取数据...")

            while current_row <= end_row:
                cell_address = f"{data_col}{current_row}"
                data_value = source_ws[cell_address].value
                if isinstance(data_value, (int, float)):
                    data_value = f"{data_value:.1%}"  # 保留两位小数的百分比格式
                
                # 无论值是什么，都先添加到列表中
                extracted_list.append(data_value)
                logging.info(f"      提取单元格 {cell_address} 的值: {data_value}")
                
                # 更新None值计数器
                if data_value is None:
                    consecutive_none_count += 1
                else:
                    consecutive_none_count = 0
                
                # 检查是否满足终止条件
                if consecutive_none_count >= 2:
                    logging.info(f"    检测到连续两次None值，提取在第 {current_row} 行提前终止。")
                    break

                current_row += step

            # --- 5. 清理并存储提取结果 ---
            # 如果循环是因为检测到两次None而中断的，移除末尾的两个None
            if consecutive_none_count >= 2:
                final_list = extracted_list[:-2]
            else:
                final_list = extracted_list

            if final_list:
                self.calculated_data['bp_target'] = final_list
                logging.info(f"    数据提取成功: {'bp_target'} 已存为包含 {len(final_list)} 个值的列表。")
            else:
                logging.warning(f"    未能从指定的序列中提取到任何数据。")

        except Exception as e:
            logging.error(f"    处理任务 'extract_bp_target' 时发生意外错误: {e}", exc_info=True)


    def _execute_extract_tila_target_job(self, job_config: dict):
        """
        (新方法) 作为“提取提拉良率目标”这个多步骤任务的总调度方法。
        """
        logging.info(" 开始执行“提取提拉良率目标”多步骤任务...")

        # 从总任务配置中获取第一步的专属配置
        step2_config = job_config.get("row_locator", {})
        step3_config = job_config.get("column_locator", {})
        
        try:
            # 调用私有辅助方法来执行第一步的具体逻辑
            product_models = self.product_models
            logging.info(f" 第一步完成：提取到 {len(product_models)} 个产品型号。")
            
             # --- 准备第二、三步所需的工作表 ---
            # 根据 step2 的配置加载工作簿和工作表
            s2_full_path = Utils.get_safe_source_path(step2_config)
            if not s2_full_path or not s2_full_path.is_file():
                logging.error(f"    未能获取有效的源文件路径，任务中止。")
                return

            s2_sheet_name = step2_config.get("sheet_name")
            source_wb = openpyxl.load_workbook(s2_full_path, read_only=True, data_only=True)
            source_ws = source_wb[s2_sheet_name]

             # --- 第二步: 为每个产品型号查找其所在的行 ---
            model_to_row_map = self.__tila_step2_find_model_rows(step2_config, product_models, source_ws)
            logging.info(f" 第二步完成：已为 {len(model_to_row_map)} 个型号定位到行。")

            # --- 第三步: 查找当前月份所在的列 (只执行一次) ---
            target_column = self.__tila_step3_find_month_column(step3_config, source_ws)
            if not target_column:
                logging.error(" 第三步失败：未能在指定行找到当前月份列，任务中止。")
                return
            logging.info(f" 第三步完成：找到当前月份所在列为 '{target_column}'。")

            # --- 第四步: 提取每个产品型号的提拉良率目标 ---
             # --- 最后一步: 整合行列信息，提取最终数值 ---
            final_values = []
            for model in product_models:
                if model in model_to_row_map:
                    target_row = model_to_row_map[model]
                    cell_address = f"{target_column}{target_row}"
                    value = source_ws[cell_address].value
                    if isinstance(value, (int, float)):
                        final_values.append(f"{value:.1%}")
                    logging.info(f" -> 型号 '{model}' (行 {target_row}) 的目标值为: {value}")
                else:
                    final_values.append(None) # 如果某个型号没找到对应的行，则添加None占位
                    logging.warning(f" -> 型号 '{model}' 未在指定列中找到，结果记为 None。")
            
            # 将最终提取到的数值列表存入 calculated_data
            self.calculated_data['tila_target'] = final_values
            logging.info(f" 任务完成: 'tila_target' 已存为包含 {len(final_values)} 个值的列表。")
        except Exception as e:
            logging.error(f" 处理任务 'extract_tila_target' 时发生意外错误: {e}", exc_info=True)
    

    
    def __tila_step2_find_model_rows(self, step2_config: dict, product_models: list, worksheet) -> dict:
        """
        (新方法) 执行提取tila_target的第二步：为每个产品型号查找其所在的行号。
        """
        search_col = step2_config.get("search_column")
        model_to_row_map = {} # 创建一个字典来存储 {型号: 行号} 的映射
        
        # 为了效率，我们只遍历一次工作表，而不是为每个型号都遍历一遍
        # 假设产品型号不会超过1000行
        for row in range(1, 1001):
            cell_address = f"{search_col}{row}"
            cell_value = worksheet[cell_address].value
            
            if isinstance(cell_value, str):
                # 检查单元格内容是否与我们的任何一个产品型号匹配
                for model in product_models:
                    if model in cell_value and model not in model_to_row_map:
                        model_to_row_map[model] = row
                        # 如果所有型号都找到了，就提前退出循环
                        if len(model_to_row_map) == len(product_models):
                            return model_to_row_map
        return model_to_row_map

    def __tila_step3_find_month_column(self, step3_config: dict, worksheet) -> str | None:
        """
        (新方法) 执行提取tila_target的第三步：在指定行中查找当前月份所在的列。
        """
        search_row = step3_config.get("search_row")
        month_format = step3_config.get("month_format")
        
        # 1. 自动计算当前月份
        current_month = dt.now().month
        search_text = (month_format or "{month}月").format(month=current_month)
        logging.info(f" 第三步：正在第 {search_row} 行查找内容包含 '{search_text}' 的单元格...")

        # 2. 遍历指定行来查找月份
        # 假设月份信息不会超过26列（Z列）
        for col in range(1, 27):
            cell = worksheet.cell(row=search_row, column=col)
            if cell.value and isinstance(cell.value, str) and search_text in cell.value:
                return cell.column_letter # 返回找到的列字母，例如 'F'
        
        return None # 如果没有找到，返回None
    
    def _execute_extract_monthly_yield_estimate_job(self, job_config: dict):
        """
        (新方法) 执行“提取月度良率预估”这个复杂任务的总调度方法。
        """
        logging.info("    开始执行“提取月度良率预估”任务...")
        
        try:
            # --- 步骤1: 动态定位源文件 ---
            file_locator_config = job_config.get("file_locator", {})
            initial_target_path = self.__find_latest_file(file_locator_config)
            if not initial_target_path: # 如果找不到文件，则返回None
                logging.error("    未能找到源文件，任务中止。")
                return
            
            source_path = Utils.resolve_lock_file(initial_target_path)
            local_cache_dir = BASE_DIR /  DATA_DIR
            source_file_path = Utils.get_local_copy(source_path, local_cache_dir)
            if not source_file_path:
                logging.error("    未能根据 file_locator 配置找到源文件，任务中止。")
                return

            # --- 步骤2: 加载工作簿和工作表 ---
            locator_config = job_config.get("cell_locator", {})
            sheet_name = locator_config.get("sheet_name")
            source_wb = openpyxl.load_workbook(source_file_path, read_only=True, data_only=True)
            source_ws = source_wb[sheet_name]
            header_row = locator_config.get("header_row", 1)

            # --- 步骤3: 定位所有需要的列 ---
            # 3.1 定位“产品型号”所在的列 (即第2个'Item'列)
            model_col_config = locator_config.get("row_locator", {})
            model_col = self.__find_column_by_header(source_ws, model_col_config, header_row)
            
            # 3.2 定位数据列
            col_locator_config = locator_config.get("column_locator", {})
            prod_yield_col_config = col_locator_config.get("production_yield_col", {})
            month_yield_col_config = col_locator_config.get("monthly_yield_col", {})
            
            prod_yield_col = self.__find_column_by_header(source_ws, prod_yield_col_config, header_row)
            month_yield_col = self.__find_column_by_format(source_ws, month_yield_col_config, header_row)

            if not all([model_col, prod_yield_col, month_yield_col]):
                logging.error("    未能定位到所有必需的列（型号、排产、当月），任务中止。")
                return
            logging.info(f"    所有关键列定位成功: 型号列={model_col}, 排产良率列={prod_yield_col}, 当月预估列={month_yield_col}")

            # --- 步骤4: 遍历产品型号，查找行并提取数据 ---
            # 从之前任务中获取产品型号列表
            product_models = self.product_models
            if not product_models:
                logging.warning("    产品型号列表为空，无法进行数据提取。")
                return

            # 为了效率，先遍历一次，构建 {型号: 行号} 的映射
            model_to_row_map = {}
            for row_idx in range(header_row + 1, source_ws.max_row + 1):
                cell_value = source_ws[f"{model_col}{row_idx}"].value
                if isinstance(cell_value, str):
                    # 检查哪个型号被包含在这个单元格里
                    for model in product_models:
                        if model in cell_value:
                            model_to_row_map[model] = row_idx
                            break # 假设一个单元格只对应一个型号

            # 根据产品型号列表的顺序，整理并提取最终数据
            production_yield_list = []
            monthly_yield_list = []
            for model in product_models:
                if model in model_to_row_map:
                    target_row = model_to_row_map[model]
                    prod_value = source_ws[f"{prod_yield_col}{target_row}"].value
                    month_value = source_ws[f"{month_yield_col}{target_row}"].value
                    production_yield_list.append(f"{prod_value:.1%}")
                    monthly_yield_list.append(f"{month_value:.1%}")
                else:
                    # 如果找不到，用None占位以保证列表顺序和长度一致
                    production_yield_list.append(None)
                    monthly_yield_list.append(None)
                    logging.warning(f"      在 {model_col} 列中未找到型号 '{model}' 对应的行。")
            
            # --- 步骤5: 存储最终结果 ---
            self.calculated_data['production_yield_values'] = production_yield_list
            self.calculated_data['monthly_yield_values'] = monthly_yield_list
            logging.info("    任务完成: 已成功提取'排产良率'和'当月预估'的数据列表。")

        except Exception as e:
            logging.error(f"    处理任务 'extract_monthly_yield_estimate' 时发生意外错误: {e}", exc_info=True)

    def __find_latest_file(self, locator_config: dict) -> Path | None:
        """(已更新) 根据配置在目录中查找最新的匹配文件，包含二级动态目录查找。"""
        base_path = Path(locator_config.get("base_path", ""))
        name_contains = locator_config.get("name_contains", "")
        dir_rule = locator_config.get("directory_rule", {}) # 获取二级目录规则

        if not base_path.is_dir():
            logging.error(f"    基础路径不存在或不是一个目录: {base_path}")
            return None

        search_path = base_path # 默认的搜索路径是基础路径
        
        # --- 第一阶段：查找最新子目录 (从本周开始向前查找) ---
        if dir_rule:
            prefix = dir_rule.get("prefix")
            if prefix:
                # 获取当前周数
                current_week = datetime.datetime.now().isocalendar()[1]
                search_paths = []
                
                # 从本周开始，向前最多查找5周
                for week_offset in range(6):  # range(6)包含0-5，共6周
                    target_week = current_week - week_offset
                    if target_week < 0:  # 如果周数变为负数，跳过
                        continue
                        
                    dir_name = f"{prefix}{target_week}"
                    dir_path = base_path / dir_name
                    
                    if dir_path.is_dir():
                        search_paths.append(dir_path)
                        logging.info(f"    找到目录: {dir_name}")
                        # 找到目录后立即尝试查找文件
                        found_file = self.__search_file_in_directory(dir_path, name_contains)
                        if found_file:
                            return found_file
                
                if not search_paths:
                    logging.warning(f"    未能在 '{base_path}' 下找到任何以 '{prefix}' 开头的子目录。")
                    return None

        # --- 第二阶段：在基础路径直接查找（如果没有二级目录规则） ---
        return self.__search_file_in_directory(base_path, name_contains)


    def __search_file_in_directory(self, directory: Path, name_contains: str) -> Path | None:
        """在指定目录中查找最新的匹配文件"""
        if not name_contains:
            return None
        
        current_month = datetime.date.today().month
        month_string_to_find = f"{current_month}月"

        latest_file = None
        latest_time = 0

        logging.info(f"    正在目录 '{directory.name}' 中查找包含 '{name_contains}' 和 '{month_string_to_find}' 的最新文件...")
        for filename in os.listdir(directory):
            if (name_contains in filename and 
                not filename.startswith('~$') and 
                month_string_to_find in filename):
                file_path = directory / filename
                if file_path.is_file():  # 确保是文件
                    mod_time = file_path.stat().st_mtime
                    if mod_time > latest_time:
                        latest_time = mod_time
                        latest_file = file_path
        
        if latest_file:
            logging.info(f"      -> 找到最新文件: {latest_file.name}")
        else:
            logging.warning(f"    未能找到包含 '{name_contains}' 的文件。")
        
        return latest_file

    
    def __find_column_by_header(self, worksheet, header_config: dict, header_row: int) -> str | None:
        """(新辅助方法) 根据表头名称和出现次数查找列。"""
        header_name = header_config.get("header_name")
        occurrence = header_config.get("occurrence", 1)
        
        count = 0
        for cell in worksheet[header_row]:
            if cell.value and isinstance(cell.value, str) and (header_name or "") in cell.value:
                count += 1
                if count == occurrence:
                    return cell.column_letter
        return None

    def __find_column_by_format(self, worksheet, format_config: dict, header_row: int) -> str | None:
        """(新辅助方法) 根据动态格式化的表头名称查找列。"""
        header_format = format_config.get("header_format")
        current_month = dt.now().month
        search_text = (header_format or "{month}月").format(month=current_month)

        for cell in worksheet[header_row]:
            if cell.value and isinstance(cell.value, str) and search_text in cell.value:
                return cell.column_letter
        return None
    

    def _execute_extract_batch_info_job(self, job_config: dict):
        """
        (新方法) “提取批次信息”的总调度方法。
        """
        logging.info("    开始执行“提取批次信息”任务...")
        
        try:
            # --- 1. 定位并加载源文件 ---
            # 从主配置中获取数据目录，并与任务配置中的文件名结合
            source_path = Utils.get_safe_source_path(job_config)
            sheet_name = job_config.get("sheet_name")
            if not source_path or not sheet_name:
                logging.error("    任务 'extract_batch_info' 配置不完整，缺少 file_name 或 sheet_name。")
                return
            source_wb = openpyxl.load_workbook(source_path, data_only=True)
            source_ws = source_wb[sheet_name]
            logging.info(f"    已成功加载源文件 '{source_path.name}' 中的工作表 '{sheet_name}'。")

             # --- 2. (新增) 构建产品型号与列范围的映射，供后续复用 ---
            model_range_map = self.__batch_info_build_model_range_map(source_ws, job_config)
            if not model_range_map:
                logging.warning(" 未能构建产品型号的列范围映射，后续步骤可能无法执行。")

            # --- 3. 执行第一部分：寻找最新批次 ---
            newest_batch_data = self.__batch_info_find_newest(source_ws, job_config, model_range_map)
            if newest_batch_data:
                self.calculated_data['newest_batch_info'] = newest_batch_data
                logging.info(" -> 第一部分完成：已成功提取'最新批次'信息。")
            
            # --- 4. 执行第二部分：寻找最优批次 ---
            best_batch_data = self.__batch_info_find_best(source_ws, job_config, model_range_map)
            if best_batch_data:
                self.calculated_data['best_batch_info'] = best_batch_data
                logging.info(" -> 第二部分完成：已成功提取'最优批次'信息。")
            
            logging.info(" 任务 'extract_batch_info' 执行完毕。")

        except Exception as e:
            logging.error(f"    处理任务 'extract_batch_info' 时发生意外错误: {e}", exc_info=True)

    def __batch_info_build_model_range_map(self, worksheet, config: dict) -> dict:
        """(新增的通用方法) 构建产品型号与其覆盖的列范围之间的映射。"""
        model_row = config.get("product_model_row")
        
        # 1. 建立起始单元格与合并范围的映射
        merge_map = {f"{worksheet.cell(r.min_row, r.min_col).column_letter}{r.min_row}": r 
            for r in worksheet.merged_cells.ranges if r.min_row == model_row}

        # 2. 查找每个产品型号的起始单元格和列范围
        model_range_map = {}
        for model in self.product_models:
            found = False
            for cell in worksheet[model_row]:
                if cell.value and isinstance(cell.value, str) and model in cell.value:
                    if cell.coordinate in merge_map:
                        # 是合并单元格
                        merged_range = merge_map[cell.coordinate]
                        model_range_map[model] = {'start_col': merged_range.min_col, 'end_col': merged_range.max_col}
                    else:
                        # 是单个单元格
                        model_range_map[model] = {'start_col': cell.column, 'end_col': cell.column}
                    found = True
                    break # 找到该型号后就去找下一个
            if not found:
                logging.warning(f" 在第 {model_row} 行未找到型号 '{model}'。")
        
        return model_range_map

    def __batch_info_find_newest(self, worksheet, config: dict, model_range_map: dict) -> dict:
        """(已重构) 寻找每个产品型号对应的最新批次信息。"""
        batch_row = config.get("batch_row")
        yield_row = config.get("ct_yield_row")
        output_rate_row = config.get("output_rate_row")
        
        results_map = {} # 改为创建字典
        for model in self.product_models:
            if model in model_range_map:
                range_info = model_range_map[model]
                latest_batch_col = range_info['end_col'] # 最新批次就是结束列

                original_batch_num = worksheet.cell(row=batch_row, column=latest_batch_col).value
                batch_num = self.__format_batch_number(original_batch_num)
                ct_yield = worksheet.cell(row=yield_row, column=latest_batch_col).value
                output_rate = worksheet.cell(row=output_rate_row, column=latest_batch_col).value
                
                raw_data = {
                "batch_number": batch_num,
                "ct_yield": ct_yield,
                "output_rate": output_rate
                }
                # 调用格式化方法并存入字典
                results_map[model] = self.__format_newest_batch_string(raw_data)
                logging.info(f" 为型号 '{model}' 找到最新批次 '{batch_num}' (位于第 {get_column_letter(latest_batch_col)} 列)。")

        return results_map
    
    def __batch_info_find_best(self, worksheet, config: dict, model_range_map: dict) -> dict:
        """(新方法) 寻找每个产品型号对应的最优批次信息。"""
        # 1. 获取配置参数
        batch_row = config.get("batch_row")
        yield_row = config.get("ct_yield_row")
        output_rate_row = config.get("output_rate_row")
        boundary = config.get("best_batch_locator", {}).get("output_rate_boundary")

        results_map = {} # 改为创建字典
        for model in self.product_models:
            if model in model_range_map:
                range_info = model_range_map[model]
        
                # 2. 筛选所有产出率达标的候选批次
                candidates = []
                for col_idx in range(range_info['start_col'], range_info['end_col'] + 1):
                    output_rate = worksheet.cell(row=output_rate_row, column=col_idx).value
                    # 确保产出率是有效的数字再进行比较
                    if isinstance(output_rate, (int, float)) and output_rate > boundary:
                        ct_yield = worksheet.cell(row=yield_row, column=col_idx).value
                        if isinstance(ct_yield, (int, float)):
                            candidates.append({'col': col_idx, 'ct_yield': ct_yield})

                # 3. 从候选中找到CT良率最高的批次
                if not candidates:
                    logging.warning(f" 型号 '{model}' 没有产出率高于 {boundary} 的候选批次。")
                    results_map[model] = "" # 如果没有最优批次，可以返回空字符串
                    continue
        
                best_candidate = max(candidates, key=lambda x: x['ct_yield'])
                best_col_idx = best_candidate['col']

                # 4. 提取最优批次的数据
                original_batch_num = worksheet.cell(row=batch_row, column=best_col_idx).value
                batch_num = self.__format_batch_number(original_batch_num)
                final_ct_yield = best_candidate['ct_yield']
                final_output_rate = worksheet.cell(row=output_rate_row, column=best_col_idx).value

                # 收集原始数据
                raw_data = {
                "batch_number": batch_num,
                "ct_yield": final_ct_yield
                }
                # 调用格式化方法并存入字典
                results_map[model] = self.__format_best_batch_string(raw_data)
                
                logging.info(f" 为型号 '{model}' 找到最优批次 '{batch_num}' (位于第 {get_column_letter(best_col_idx)} 列)。")
                
        return results_map
    
    def __format_batch_number(self, original_batch: str) -> str:
        """(新辅助方法) 将原始批次号格式化为 '月/日批次' 的形式。"""
        if not isinstance(original_batch, str):
            return original_batch # 如果输入不是字符串，直接返回原值

        # 正则表达式匹配 '任意两位数字/两位数字/两位数字' 开头的字符串
        # 并捕获第一个和第二个'两位数字'（即月和日）
        match = re.search(r'^\d{2}/(\d{2})/(\d{2})', original_batch)
        
        if match:
            # 如果匹配成功，group(1)是月份，group(2)是日期
            month = match.group(1)
            day = match.group(2)
            return f"{month}/{day}批次"
        else:
            # 如果不匹配，返回原始字符串并记录警告，避免程序出错
            logging.warning(f"    批次号 '{original_batch}' 格式不符合预期，未进行格式化。")
            return original_batch
    
    def __format_newest_batch_string(self, data: dict) -> str:
        """(新辅助方法) 将最新批次信息字典格式化为标准字符串。"""
        # 检查所需数据是否存在且有效
        batch = data.get("batch_number", "")
        ct_yield = data.get("ct_yield")
        output_rate = data.get("output_rate")

        # 使用f-string的百分比格式化功能，例如 0.889 -> 88.9%
        yield_str = f"{ct_yield:.1%}" if isinstance(ct_yield, (int, float)) else "N/A"
        output_str = f"{output_rate:.1%}" if isinstance(output_rate, (int, float)) else "N/A"

        return f"{batch}CT良率{yield_str}，产出率{output_str}"

    def __format_best_batch_string(self, data: dict) -> str:
        """(新辅助方法) 将最优批次信息字典格式化为标准字符串。"""
        batch = data.get("batch_number", "")
        ct_yield = data.get("ct_yield")

        yield_str = f"{ct_yield:.1%}" if isinstance(ct_yield, (int, float)) else "N/A"

        return f"{batch}CT良率{yield_str}"

    def _execute_extract_risk_items_job(self, job_config: dict):
        """
        (新方法) “提取风险品信息”的总调度方法。
        """
        logging.info("    开始执行“提取风险品信息”任务...")
        
        try:
             # --- 第一部分：提取风险品良率数据 ---
            yield_finder_config = job_config.get("risk_yield_finder")
            yield_data_map = {}
            if yield_finder_config:
                yield_data_map = self.__risk_items_find_yield_data(yield_finder_config)
                logging.info("      -> 第一部分完成：已提取'风险品良率数据'。")

            # --- 第二部分：提取风险品释放计划 ---
            release_plan_config = job_config.get("release_plan_finder")
            release_plan_map = {}
            if release_plan_config:
                # 将第一部分的结果作为输入，以确保只查找相关的风险品
                release_plan_map = self.__risk_items_find_release_plan(release_plan_config, yield_data_map)
                logging.info("      -> 第二部分完成：已提取'风险品释放计划'。")

            # --- 第三部分：合并数据并生成最终字符串 ---
            final_risk_items_map = {}
            logging.info("      -> 第三部分开始：合并数据并生成最终报告字符串...")
            for model, risk_items in yield_data_map.items():
                final_risk_items_map[model] = {}
                for risk_name, yield_str in risk_items.items():
                    # 从释放计划map中查找对应的计划
                    plan_str = release_plan_map.get(model, {}).get(risk_name, "")
                    
                    # 按照您要求的标准格式拼接
                    # 格式：风险品名称：良率数据，释放计划
                    final_str = f"{risk_name}：{yield_str}"
                    if plan_str: # 如果有释放计划，则用逗号拼接
                        final_str += f"，{plan_str}"
                    
                    final_risk_items_map[model][risk_name] = final_str
            
            # 存储最终的、已合并的、格式化好的结果
            if final_risk_items_map:
                self.calculated_data['risk_items'] = final_risk_items_map
                logging.info("      -> 所有部分完成：已生成最终的风险品信息。")
            
            logging.info("    任务 'extract_risk_items' 执行完毕。")

        except Exception as e:
            logging.error(f"    处理任务 'extract_risk_items' 时发生意外错误: {e}", exc_info=True)


    def __risk_items_find_yield_data(self, config: dict) -> dict:
        """
        (新辅助方法) 根据配置，提取每个产品型号下的风险品及其对应的月度良率数据。
        """
        # --- 1. 解析并验证配置 ---
        source_path = Utils.get_safe_source_path(config)
        sheet_name = config.get("sheet_name")
        if not source_path or not sheet_name:
            logging.error(f"    未能获取有效的源文件路径，任务中止。")
            return {}
        
        worksheet = openpyxl.load_workbook(source_path, data_only=True)[sheet_name]
        
        # --- 2. 获取风险品数据表结构定义 ---
        model_locator_cfg = config.get("product_model_locator", {})
        item_def_cfg = config.get("risk_item_definition", {})
        
        model_col = model_locator_cfg.get("search_column")
        risk_item_col = item_def_cfg.get("item_column")
        ignore_values = set(item_def_cfg.get("ignore_values", [])) # 使用set提高查找效率
        data_cols = item_def_cfg.get("data_columns", [])
        data_header_row = item_def_cfg.get("data_header_row")

        # --- 3. 获取数据列的表头（月份） ---
        header_map = {col: worksheet[f"{col}{data_header_row}"].value for col in data_cols}
        
        # --- 4. 构建产品型号的纵向合并单元格范围映射 ---
        model_range_map = {}
        for merged_range in worksheet.merged_cells.ranges:
            # 检查合并是否发生在我们的目标列
            if merged_range.min_col == column_index_from_string(model_col):
                model_name_cell = worksheet.cell(row=merged_range.min_row, column=merged_range.min_col)
                if model_name_cell.value in self.product_models:
                    model_range_map[model_name_cell.value] = merged_range

        # --- 5. 遍历每个产品型号，查找其下的风险品和数据 ---
        final_results = {}
        for model in self.product_models:
            if model not in model_range_map:
                logging.warning(f"        在 {sheet_name} 表中未找到型号 '{model}' 对应的合并单元格区域。")
                continue

            merged_range = model_range_map[model]
            model_risk_items_dict = {} # 改为创建字典
            
            # 遍历该型号覆盖的所有行
            for row_idx in range(merged_range.min_row, merged_range.max_row + 1):
                risk_item_name = worksheet[f"{risk_item_col}{row_idx}"].value

                # 检查是否是有效的风险品
                if risk_item_name and str(risk_item_name).strip() not in ignore_values:
                    # 提取该风险品对应的良率数据
                    yield_data = {}
                    for col_letter in data_cols:
                        month_header = header_map.get(col_letter)
                        if month_header: # 确保表头存在
                            yield_value = worksheet[f"{col_letter}{row_idx}"].value
                            yield_data[month_header] = yield_value
                
                    formatted_yield_str = self.__format_risk_yield_string(yield_data)
                     # (核心改动) 存入新的嵌套字典结构
                    model_risk_items_dict[risk_item_name] = formatted_yield_str
            
            final_results[model] = model_risk_items_dict
            logging.info(f" 为型号 '{model}' 找到 {len(model_risk_items_dict)} 个风险品并格式化良率。")
            
        return final_results
    
    def __risk_items_find_release_plan(self, config: dict, yield_data_map: dict) -> dict:
        """
        (新方法) 提取每个风险品对应的释放计划。
        """
        # --- 1. 解析并验证配置 ---
        full_path = Utils.get_safe_source_path(config)
        sheet_name = config.get("sheet_name")
        if not full_path or not sheet_name:
            logging.error(f"    未能获取有效的源文件路径，任务中止。")
            return {}
        worksheet = openpyxl.load_workbook(full_path, data_only=True)[sheet_name]
        
        header_row = config.get("header_row", 1)
        model_col_header = config.get("product_model_column")
        risk_col_header = config.get("risk_item_column")
        plan_col_header = config.get("release_plan_column")

        # --- 2. 定位关键列 ---
        model_col = self.__find_column_by_header(worksheet, {'header_name': model_col_header}, header_row)
        risk_col = self.__find_column_by_header(worksheet, {'header_name': risk_col_header}, header_row)
        plan_col = self.__find_column_by_header(worksheet, {'header_name': plan_col_header}, header_row)
        if not all([model_col, risk_col, plan_col]):
            logging.error("    未能在释放计划表中定位到所有必需的列。")
            return {}

        # --- 3. 构建 (型号, 风险品) -> 释放计划 的查询字典，以提高效率 ---
        plan_lookup_map = {}
        for row_idx in range(header_row + 1, worksheet.max_row + 1):
            model = worksheet[f"{model_col}{row_idx}"].value
            risk = worksheet[f"{risk_col}{row_idx}"].value
            plan = worksheet[f"{plan_col}{row_idx}"].value
            if model and risk:
                # 使用元组 (model, risk) 作为唯一的键
                plan_lookup_map[(str(model).strip(), str(risk).strip())] = plan

        # --- 4. 遍历第一部分的结果，查找并构建输出字典 ---
        release_plan_results = {}
        for model, risk_items in yield_data_map.items():
            release_plan_results[model] = {}
            for risk_name in risk_items.keys():
                # 在查询字典中查找释放计划
                plan = plan_lookup_map.get((model, risk_name))
                if plan:
                    release_plan_results[model][risk_name] = str(plan)
        
        return release_plan_results

    def __format_risk_yield_string(self, yield_data: dict) -> str:
        """
        (新辅助方法) 将良率数据字典格式化为 'M08 1.14%，M09 0.98%' 的字符串。
        """
        parts = []
        for month_header, value in yield_data.items():
            # 确保值是数字类型
            if not isinstance(value, (int, float)):
                continue
            
            # 从表头（如 '8月'）中提取月份数字
            month_match = re.search(r'(\d+)', str(month_header))
            if not month_match:
                continue
        
            month_num = int(month_match.group(1))
        
            # 使用 Python 的格式化功能，自动处理补零和百分比转换
            # 例如: M{8:02} {0.0114:.2%} -> M08 1.14%
            formatted_part = f"M{month_num:02} {value:.2%}"
            parts.append(formatted_part)
        
        # 使用中文逗号将各部分连接起来
        return "，".join(parts)
