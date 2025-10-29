# src/exception_processor.py
import datetime
import logging, re, json
import pandas as pd
from pathlib import Path
from typing import Optional

from excel_generator_project.utils.utils import Utils
from excel_generator_project.config import TEMP_DIR
from excel_generator_project.infrastructure.excel_handler import ExcelHandler
from openpyxl.utils import get_column_letter

class ExceptionProcessor:
    """
    专门负责处理“CT良率异常波动管理表”相关业务逻辑的处理器。
    (已重构为调度器模式)
    """
    def __init__(self, config: dict):
        """
        初始化异常处理器。
        :param config: 完整的、从 config.yaml 加载的配置字典。
        """
        self.config = config
        self.templates = config.get('report_text_templates', {})
        self.processed_results = {}  # 用于存储本处理器所有任务的最终结果
        self.intermediate_data = {} 
        self.cache_dir = TEMP_DIR
        # ‘model_definitions’可以确保提取的产品型号是从最新日报中提取的
        self.product_models = Utils.extract_product_models(config.get('model_definitions', []))
        logging.info("ExceptionProcessor 初始化成功。")

    def run(self):
        """
        主调度方法。
        """
        logging.info("--- ExceptionProcessor 开始运行 ---")
        # --- 步骤 1: 准备输出文件和Excel处理器 ---
        
        jobs = self.config.get('exception_processing_jobs', [])
        logging.info(f"发现 {len(jobs)} 个异常处理任务...")

        for i, job_config in enumerate(jobs, 1):
            job_type = job_config.get("job_type")
            logging.info(f"--> 开始执行任务 {i}/{len(jobs)}: 类型 = {job_type}")

            if job_type == "extract_previous_exceptions": # 步骤1: 提取上一版日报中的异常记录
                self._execute_extract_previous_exceptions(job_config)
            elif job_type == "extract_daily_exception": # 步骤2: 提取当日异常内容
                self._execute_extract_daily_exception(job_config)
            elif job_type == "format_exception_report": # 步骤3: 当日异常格式化
                self._execute_format_exception_report(job_config)
            elif job_type == "merge_daily_into_previous": # 步骤4： 将当日异常到上一版日报中的异常记录中
                self._execute_merge_daily_into_previous(job_config)
            else:
                logging.warning(f"未知的任务类型 '{job_type}'，已跳过。")
        
        # --- 核心修改：将不安全的循环替换为直接打印整个结果字典 ---
        logging.info("--- 所有任务执行完毕，最终数据结构如下 ---")
        # 这会打印出所有被成功处理的产品的完整数据，更安全也更直观
        logging.info(json.dumps(self.processed_results, ensure_ascii=False, indent=2))

        logging.info("--- ExceptionProces   sor 运行结束 ---")
        return self.processed_results
        # --- 使用以下修正后的代码替换原方法 ---

    def _execute_extract_previous_exceptions(self, job_config: dict):
        """
        (任务3, 再次修正) 从上一版日报中，按顺序为每个产品提取原异常记录。
        """
        logging.info("  开始执行'提取昨日异常记录'任务...")

        current_hour = datetime.datetime.now().hour
        logging.info(f"    当前小时: {current_hour}点。文本转换将在12点后激活。")

        # --- 核心修改：采用“业务类查找 -> 工具类复制”的新模式 ---
        # 1. 调用专属的私有方法来定位远程源文件
        dynamic_path_cfg = job_config.get("dynamic_path_config", {})
        source_path = self.__find_previous_report_file(dynamic_path_cfg)
        if not source_path:
            logging.error("    未能根据 dynamic_path_config 找到源文件，任务中止。")
            return
        
        # --- 核心修改 1: 将路径存入新的 intermediate_data 字典 ---
        self.intermediate_data['previous_exceptions_source_path'] = source_path
        logging.info(f"    已记录上一版日报的源文件路径: {source_path.name}")
        # --- 修改结束 ---

        # 2. 依次调用通用的Utils函数，进行路径净化和复制
        # (假设 resolve_lock_file 已存在于 Utils 中)
        source_path_resolved = Utils.resolve_lock_file(source_path)
        source_file_path = Utils.get_local_copy(source_path_resolved, self.cache_dir)
        if not source_file_path:
            logging.error("    复制远程文件到本地缓存失败，任务中止。")
            return

        
        try:
            df = self._get_data_as_dataframe(source_file_path, job_config['sheet_name'])
            data_column_index = df.columns.get_loc(job_config['data_column'])
        except Exception as e:
            logging.error(f"  加载数据或获取列索引失败: {e}")
            return

        # --- 新增：从配置中获取转换规则 ---
        transformations = job_config.get('text_transformations', [])
        product_models = Utils.extract_product_models(self.config.get('model_definitions', []), source_file_path)
        for product_index, model in enumerate(product_models):
            extracted_modules = {}
            logging.info(f"    正在为产品 '{model}' (序号 {product_index}) 提取旧有记录...")
            
            # (模块定义和循环部分代码不变)
            module_definitions = job_config.get('sequential_extraction_rules', {}).get('module_definitions', [])
            for module_def in module_definitions:
                target_df_index = (module_def['start_row'] - 2) + (product_index * module_def['step'])
                key_name = module_def['key_name']

                try:
                    # 使用 .iat 进行高性能、精确的单点值访问
                    cell_content = df.iat[target_df_index, data_column_index]

                    # 步骤1：检查是否为空，如果不为空，则转换为字符串并执行替换和清理
                    if pd.isna(cell_content):
                        processed_content = ""
                    else:
                        # 转换为字符串。精确替换 "無\n"。使用 .strip() 清理替换后可能留下的首尾空白
                        processed_content = str(cell_content).replace("无\n", "").strip()
                    
                    # 步骤 2: 应用更复杂的文本转换规则
                    if current_hour >= 12 and transformations:
                        final_content = self._apply_text_transformations(processed_content, transformations)
                    else:
                        final_content = processed_content
                    
                    extracted_modules[key_name] = final_content
                except IndexError:
                    logging.error(f"      计算出的行索引 {target_df_index} 超出范围，无法为 '{model}' 提取 '{key_name}'。")
                    extracted_modules[key_name] = "错误：行越界"

            if model not in self.processed_results:
                self.processed_results[model] = {}
            
            self.processed_results[model]['previous_exceptions'] = extracted_modules
            logging.info(f"    -> 已为 '{model}' 存入 {len(extracted_modules)} 个旧有记录模块。")

    def _execute_extract_daily_exception(self, job_config: dict):
        """(任务执行方法) 使用Parquet缓存高效地提取每日异常数据。"""
        today = datetime.date.today()
        date_to_find = today.strftime('%m/%d')
        
        source_path = Utils.get_safe_source_path(job_config)
        if not source_path or not source_path.is_file():
            logging.error(f"    未能获取有效的源文件路径，任务中止。")
            return
        
        # 步骤 1: 使用新的缓存方法获取DataFrame
        try:
            df = self._get_data_as_dataframe(source_path, job_config['sheet_name'])
        except Exception as e:
            logging.error(f"无法加载源数据或创建缓存: {e}", exc_info=True)
            return

        # --- 核心修改 2: 重构数据筛选逻辑以使用来自前一任务的路径 ---
        logging.info("  正在执行数据筛选...")
        date_col = job_config['date_column']
        
        # 将日期列转换为日期时间格式，并检查是否所有值都为空
        # 1. 强制转换为字符串并清除首尾空格
        cleaned_date_series = df[date_col].astype(str).str.strip()
        # 2. 在清理后的数据上进行日期时间转换
        datetime_series = pd.to_datetime(cleaned_date_series, errors='coerce')
        if datetime_series.isnull().all():
            logging.warning(f"  日期列 '{date_col}' 中所有值都无法解析为有效日期，任务中止。")
            return
        date_filter = (datetime_series.dt.date == today)

        # 默认不应用时间过滤器
        time_filter = pd.Series(True, index=df.index) 
        previous_report_path = self.intermediate_data.get('previous_exceptions_source_path')
        # 根据前一任务找到的文件名，条件性地激活时间过滤器
        if previous_report_path and "14：00" in previous_report_path.name:
            logging.info(f"  检测到上一版日报为 '{previous_report_path.name}'，已激活14:30之后的时间过滤器。")
            time_filter = (datetime_series.dt.time >= datetime.time(14, 30))
        
        combined_filter = date_filter & time_filter
        todays_df = df[combined_filter].copy()

        if todays_df.empty:
            logging.info(f"在 '{source_path.name}' 中未找到日期为 '{date_to_find}' 的记录。")
            return

        # --- 核心修改：在这里增加数据清洗步骤 ---
        product_model_col = job_config['product_model_column']
        
        # 1. 强制净化DataFrame中的产品型号列
        logging.info("  [净化] 正在清理DataFrame中的产品型号列...")
        todays_df[product_model_col] = todays_df[product_model_col].astype(str).str.strip()

        # 步骤 3: 遍历产品型号，并在DataFrame中查找匹配的数据
        for model in self.product_models:
            logging.info(f"正在为产品 '{model}' 查找异常数据...")

            # 2. 净化 self.product_models 中的当前型号
            clean_model = str(model).strip()
            model_data = todays_df[todays_df[product_model_col] == clean_model]
            
            if not model_data.empty:
                # 提取第一条匹配记录的数据
                record = model_data.iloc[0]
                logging.info(f"  --> 找到匹配 '{model}' 的记录，开始解析。")
                factory = record.get(job_config['factory_column'], "")
                factory_str = "" if pd.isna(factory) else str(factory).upper().strip()

                title_text = record[job_config['title_column']]
                details_text = record[job_config['details_column']]
                
                parsed_title = self._parse_text_with_patterns(title_text, job_config.get('title_patterns', {}))
                parsed_details = self._parse_text_with_patterns(details_text, job_config.get('details_patterns', {}))
                
                raw_data = parsed_title | parsed_details
                raw_data['factory'] = factory_str # 将厂别信息存入raw_data

                # 在 self.processed_results 中为该型号创建主键
                if model not in self.processed_results:
                    self.processed_results[model] = {}
                # 将提取的原始数据存入 'raw_data' 子字典
                self.processed_results[model]['raw_data'] = raw_data


    def _parse_text_with_patterns(self, text: str, patterns: dict) -> dict:
        """(辅助方法) 使用指定的正则表达式字典来解析一段文本。"""
        parsed_data = {}
        if not text:
            return parsed_data
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                parsed_data[key] = match.group(1).strip()
            else:
                parsed_data[key] = "N/A"
                logging.warning(f"配置的 '{key}' 正则表达式未在文本中找到匹配项。")
        return parsed_data
    
    def _get_data_as_dataframe(self, excel_path: Path, sheet_name: str) -> pd.DataFrame:
        """
        (新增辅助方法)
        智能地从Excel或Parquet缓存中加载数据。
        如果缓存不存在或已过期，则从Excel转换并创建缓存。
        """
        if not excel_path.exists():
            raise FileNotFoundError(f"源Excel文件不存在: {excel_path}")

        # 根据源文件名和工作表名创建唯一的缓存文件名
        cache_file_name = f"{excel_path.stem}_{sheet_name}.parquet"
        cache_path = self.cache_dir / cache_file_name

        # 检查缓存是否有效
        is_cache_valid = False
        if cache_path.exists():
            excel_mtime = excel_path.stat().st_mtime
            cache_mtime = cache_path.stat().st_mtime
            if cache_mtime > excel_mtime:
                is_cache_valid = True

        if is_cache_valid:
            # 缓存有效，直接从Parquet读取
            logging.info(f"加载有效的缓存文件: {cache_path.name}")
            return pd.read_parquet(cache_path)
        else:
            # 缓存无效或不存在，从Excel读取并创建/更新缓存
            logging.warning(f"缓存无效或不存在，正在从源Excel文件 '{excel_path.name}' 创建缓存...")
            # 使用pandas读取Excel，更快
            df = pd.read_excel(excel_path, sheet_name=sheet_name)

            # --- 新增的修复代码 ---
            # 在保存为Parquet前，将所有object类型的列强制转换为字符串
            # 这是为了防止因列中混合了数字和文本而导致的 ArrowTypeError
            logging.info("正在进行数据类型预处理...")
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str)
            logging.info("数据类型预处理完成。")
            # --- 修复代码结束 ---
            
            # 保存为Parquet格式
            df.to_parquet(cache_path, index=False)
            logging.info(f"缓存已成功创建: {cache_path.name}")
            return df
    
    def _execute_format_exception_report(self, job_config: dict):
        """(任务2, 已重构) 为每个产品生成报告段落，并添加到各自的子字典中。"""
        if not self.processed_results:
            logging.warning("没有可供格式化的原始数据，格式化任务已跳过。")
            return

        title_template = self.templates.get('exception_report_title')
        details_template = self.templates.get('exception_report_details')
        if not title_template or not details_template:
            logging.error("报告模板 'exception_report_title' 或 'exception_report_details' 未找到。")
            return

        month_str = datetime.date.today().strftime('M%m')
        
        # 遍历 self.processed_results 中已有的产品型号
        for model, model_data in self.processed_results.items():
            raw_data = model_data.get('raw_data')
            
            # 仅当该产品有原始数据时才进行格式化
            if raw_data:
                data_for_title = raw_data.copy()

                # 格式化细节1: 去掉单引号
                if 'exception_name' in data_for_title:
                    data_for_title['exception_name'] = str(data_for_title['exception_name']).replace("'", "")

                # 格式化细节3: 统一序号
                title_format_data = {'index': "1.1", 'month_str': month_str, **data_for_title}
                
                # 假设 format_string 已移至 Utils
                title_part = Utils.format_string(title_template, title_format_data)
                details_part = Utils.format_string(details_template, raw_data)
                
                # 格式化细节2: 确保单换行
                report_paragraph = f"{title_part.strip()}\n{details_part.strip()}"

                # 将生成的段落添加回该产品型号的子字典中
                self.processed_results[model]['report_paragraph'] = report_paragraph



    # --- 新增的私有辅助方法 ---
    def __find_previous_report_file(self, dynamic_config: dict) -> Optional[Path]:
        """
        (新增) 专用于本任务的、根据年月动态查找最新报告文件的私有方法。
        """
        base_path_str = dynamic_config.get("base_path")
        subdir_pattern = dynamic_config.get("subdirectory_pattern")
        file_pattern = dynamic_config.get("file_pattern")

        if not all([base_path_str, subdir_pattern, file_pattern]):
            logging.error("    dynamic_path_config 配置不完整，缺少 base_path, subdirectory_pattern 或 file_pattern。")
            return None
        if not isinstance(subdir_pattern, str) or not isinstance(base_path_str, str) or not isinstance(file_pattern, str):
                logging.error(" 路径组件必须都是字符串类型。")
                return None

        try:
            # 1. 根据当前日期构建子目录路径
            today = datetime.date.today()
            
            subdir_name = subdir_pattern.format(year=today.year, month=today.month)
            search_path = Path(base_path_str) / subdir_name

            if not search_path.is_dir():
                logging.warning(f"    动态构建的搜索目录不存在: '{search_path}'")
                return None

            # 2. 复用通用的 find_latest_valid_file 工具函数来查找最终文件
            # (假设此函数已存在于 Utils 中)
            latest_file = Utils.find_latest_valid_file(str(search_path), file_pattern)
            return latest_file
            
        except Exception as e:
            logging.error(f"    在动态查找文件时发生错误: {e}", exc_info=True)
            return None
        
    
        
    def _apply_text_transformations(self, text: str, transformations: list) -> str:
        """
        (已更新) 根据配置规则，对输入的文本进行一系列转换操作。
        使用替换函数来安全地处理包含特殊字符的文本。
        """
        if not text:
            return ""

        transformed_text = text
        for rule in transformations:
            rule_name = rule.get("rule_name")
            logging.info(f"      应用文本转换规则: '{rule_name}'")

            if rule_name == "move_down_daily_exception":
                source_pattern = rule.get('source_pattern')
                destination_pattern = rule.get('destination_pattern')
                
                if not source_pattern or not destination_pattern:
                    continue

                match = re.search(source_pattern, transformed_text)
                
                if match:
                    block_to_move = match.group(2).strip()
                    block_to_move = re.sub(r'^1\.', '2.', block_to_move)
                    text_after_cut = re.sub(source_pattern, r'\1\3', transformed_text, count=1).strip()
                    
                    # --- 核心修改：使用替换函数来安全地执行“粘贴” ---
                    def replacer(match_obj):
                        # match_obj.group(1) 是 destination_pattern 匹配到的内容 (即 "2、各工厂还原时序\n")
                        # block_to_move 在这里被当作纯文本字符串，不会被re引擎解析
                        return f"{match_obj.group(1)}{block_to_move}\n"

                    final_text = re.sub(destination_pattern, replacer, text_after_cut, count=1)
                    # --- 修改结束 ---
                    
                    transformed_text = final_text

            elif rule_name == "cleanup_daily_exception_section":
                pattern = rule.get('pattern')
                replacement = rule.get('replacement')

                if pattern and replacement is not None:
                    transformed_text = re.sub(pattern, replacement, transformed_text)

        return transformed_text
    
    def _execute_merge_daily_into_previous(self, job_config: dict):
        """(任务4) 将当日异常根据厂别，合并到前一日的异常记录模块中。"""
        logging.info("  开始执行'合并当日异常'任务...")
        routing_rules = job_config.get('factory_routing_rules', {})
        insertion_pattern = job_config.get('insertion_pattern')

        if not routing_rules or not insertion_pattern:
            logging.error("  'factory_routing_rules' 或 'insertion_pattern' 配置缺失，任务中止。")
            return
        
        for model, model_data in self.processed_results.items():
            # 1. 获取该型号所需的所有数据
            raw_data = model_data.get('raw_data', {})
            factory = raw_data.get('factory', 'UNKNOWN')
            
            report_paragraph = model_data.get('report_paragraph')
            previous_exceptions = model_data.get('previous_exceptions')

            if not report_paragraph or not previous_exceptions:
                logging.info(f"    产品 '{model}'没有当日异常。")
                continue

            # 2. 根据厂别进行路由
            target_module_key = routing_rules.get(factory)
            if not target_module_key:
                logging.warning(f"    产品 '{model}' 的厂别 '{factory}' 没有匹配的路由规则，跳过合并。")
                continue
            
            # 3. 获取待修改的文本模块
            target_text = previous_exceptions.get(target_module_key)
            if target_text is None:
                logging.warning(f"    产品 '{model}' 在旧有记录中未找到目标模块 '{target_module_key}'，跳过合并。")
                continue

            # 4. 执行安全的插入操作
            logging.info(f"    正在将产品 '{model}' 的异常报告插入到 '{target_module_key}'...")
            def replacer(match_obj):
                # match_obj.group(1) 是捕获的 "1、当日异常\n"
                # report_paragraph 在此被视为纯文本，安全地插入
                return f"{match_obj.group(1)}{report_paragraph}\n"
            
            # count=1 确保只替换第一个匹配项
            modified_text = re.sub(insertion_pattern, replacer, target_text, count=1)

            # 5. 将修改后的文本写回 self.processed_results
            self.processed_results[model]['previous_exceptions'][target_module_key] = modified_text

    # def _execute_write_processed_exceptions(self, job_config: dict):
    #     """
    #     (新增任务) 将最终处理好的异常模块文本，按顺序写回到目标Excel文件的单元格中。
    #     """   
    #     if not self.excel_handler:
    #         logging.error("  ExcelHandler 未初始化，无法执行写入任务。")
    #         return

    #     logging.info("  开始执行'写入已处理异常'任务...")
    #     sheet_name = job_config['sheet_name']
    #     data_column_name = job_config['data_column']
    #     rules = job_config.get('sequential_extraction_rules', {})
    #     module_definitions = rules.get('module_definitions', [])

    #     try:
    #         self.excel_handler.set_active_sheet(sheet_name)
    #         if not self.excel_handler or not self.excel_handler.ws:
    #             logging.error("  工作表未正确初始化，无法执行写入操作")
    #             return
            
    #         # 从表头找到目标列的索引，进而得到列字母
    #         header_row = self.excel_handler.ws[1]
    #         col_idx = None
    #         for cell in header_row:
    #             if cell.value == data_column_name:
    #                 col_idx = cell.column
    #                 break
            
    #         if col_idx is None:
    #             logging.error(f"  在工作表 '{sheet_name}' 中未找到列标题 '{data_column_name}'。")
    #             return
            
    #         col_letter = get_column_letter(col_idx)

    #     except Exception as e:
    #         logging.error(f"  准备写入时出错（例如，工作表不存在）: {e}", exc_info=True)
    #         return

    #     # 遍历每个产品，计算位置并写入数据
    #     for product_index, model in enumerate(self.product_models):
    #         processed_data = self.processed_results.get(model, {}).get('previous_exceptions', {})
            
    #         for module_def in module_definitions:
    #             key_name = module_def['key_name']
    #             text_to_write = processed_data.get(key_name, "错误: 未找到已处理的文本")

    #             start_row = module_def['start_row']
    #             step = module_def['step']
    #             target_row = start_row + (product_index * step)
                
    #             target_cell_address = f"{col_letter}{target_row}"
    #             logging.info(f"    正在将产品 '{model}' 的 '{key_name}' 写入到单元格 {target_cell_address}")
    #             self.excel_handler.write_cell(target_cell_address, text_to_write)