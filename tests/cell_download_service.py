import logging
import time, datetime
from src.cell_yield.config import CellYieldConfig
from packages.web_automation.src.application.download_service import DownloadService
from src.cell_yield.infrastructure.cell_portal_adapter import CellPortalAdapter

logger = logging.getLogger("CellDownloadService")

class CellDownloadService(DownloadService):
    """
    [Domain Service] 屏体良率 (Cell Yield) 报表下载业务编排服务
    """

    def __init__(self, config: CellYieldConfig):
        super().__init__(config) # type: ignore
        self.config = config

    def run_download_tasks(self):
        logger.info(">>> 启动 Cell 领域专属报表下载管线 <<<")
        try:
            self.page = self.start_engine()
            self.portal_adapter = CellPortalAdapter(self.page, self.config.browser.timeout)

            self.portal_adapter.navigate_to_home(self.config.daily_report.portal_url)
            if self.config.daily_report.username:
                self.portal_adapter.login(self.config.daily_report.username, self.config.daily_report.password)

            reports = self.config.daily_report.reports
            for i, report in enumerate(reports):
                logger.info(f"--- 处理业务报表 [{i+1}/{len(reports)}]: {report.name} ---")
                
                try:
                    self.portal_adapter.search_and_enter_report(report.name, report.path)
                    
                    if report.name == "V3入库不良率加权报表":
                        self._handle_v3_report_workflow(report)
                    else:
                        self.portal_adapter.fr_click_query()
                        self.portal_adapter.fr_wait_for_report_ready()
                        self.portal_adapter.fr_export_excel_original()
                        
                    self.portal_adapter.reset_search_state()
                    time.sleep(1)

                except Exception as e:
                    logger.error(f"报表 {report.name} 处理出错: {e}")
                    # ==========================================
                    # 🚦 调试模式：遇到错误时挂起！
                    # ==========================================
                    logger.warning("🛑 遇到错误！脚本已暂停，请直接去浏览器查看现场。")
                    if self.page:
                        self.page.pause()  # 程序将在这里永远卡住，直到您手动放行
                    # ==========================================
                    self.portal_adapter.reset_search_state()
                    continue

        except Exception as e:
            logger.critical(f"Cell 下载管线崩溃: {e}")
            raise
        finally:
            self._handle_shutdown()

    def _get_last_sunday(self) -> str:
        """
        [内部方法] 计算“上周六”的精确日期，自动处理跨月跨年。
        返回格式: 'YYYY-MM-DD'
        """
        today = datetime.date.today()
        # today.weekday() 返回 0-6 分别代表周一到周日。
        # 例如：今天是周一(0)，退 2 天就是上周六
        days_offset = today.weekday() + 2
        last_sunday = today - datetime.timedelta(days=days_offset)
        return last_sunday.strftime("%Y-%m-%d")

    def _handle_v3_report_workflow(self, report):
        """V3 报表的专属循环逻辑子流程"""
        logger.info("启用 V3 报表专属循环下载模式...")
        
        try:
            # 【全新增加的第一步】：自动计算并设置“结束日期”为上周六
            last_sunday_str = self._get_last_sunday()
            logger.info(f"执行业务逻辑: 自动设定结束日期为上周六 ({last_sunday_str})...")
            # 直接调用底层适配器刚写好的日期输入方法
            self.portal_adapter.fr_fill_date_by_label("结束日期:", last_sunday_str)
            
            # A. 设置一次性的公共筛选条件（外部不需要循环的条件）
            self.portal_adapter.set_v3_month_and_week("5")
            
            # 【原有的第四步】：设置特定的 Group 多选
            target_groups = ["外观不良", "屏体制造", "屏体技术部", "检测技术部"]
            logger.info("执行业务逻辑: 设定特定 Group 组合...")
            self.portal_adapter.select_v3_defect_groups(target_groups)
            
            types_to_fetch = self.config.daily_report.product_types
            for p_type in types_to_fetch:
                logger.info(f"  >>> 开始处理子任务: 产品类型 [{p_type}] <<<")
                try:
                    self.portal_adapter.select_v3_product_type(p_type)
                    self.portal_adapter.select_v3_all_product_models()
                    
                    self.portal_adapter.fr_click_query()
                     
                    if report.wait_text:
                        self.portal_adapter.fr_wait_for_specific_text(report.wait_text)
                    else:
                        self.portal_adapter.fr_wait_for_report_ready()
                        
                    # 组装完美的文件名（注：根据上一轮排查，这里务必使用 .xls 后缀）
                    expected_filename = f"{report.name}_{p_type}.xls"
                    
                    # 将“点击动作”作为一个函数对象传给底层去执行并安全等待
                    self.perform_download_action(
                        action_callable=self.portal_adapter.fr_export_excel_original,
                        file_name=expected_filename
                    )
                    
                    # 给系统一个微小的缓冲时间，准备迎接下一个循环
                    time.sleep(1) 
                    
                except Exception as sub_e:
                    logger.error(f"产品类型 [{p_type}] 处理失败，将跳过: {sub_e}")
                    if self.page: self.page.pause()
                    continue
                    
        except Exception as flow_e:
            logger.error(f"V3 报表前置条件设置失败: {flow_e}")
            raise flow_e