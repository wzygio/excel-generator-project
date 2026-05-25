"""
yield_portal_adapter.py: 良率报表领域 PortalAdapter

【职责】
    继承 OLEDPortalAdapter，封装 V3 良率报表（月周天汇总/批次汇总）特有的 UI 操作。

【红线】
    - 只包含 UI 交互逻辑，不含业务流程编排
    - 标签文本（如 "结束日期:"、"产品型号:"）作为可配置参数，方便调试时调整
"""

from __future__ import annotations

import logging

from fr_web_automation.infrastructure.playwright_adapter import OLEDPortalAdapter

logger = logging.getLogger("YieldPortalAdapter")


class YieldPortalAdapter(OLEDPortalAdapter):
    """
    良率报表领域 PortalAdapter。

    提供 V3 良率报表参数面板的原子操作：
    - 日期选择器设置
    - 下拉复选框（产品型号等）选择
    - 查询按钮触发
    - 导出操作
    """

    # ================================================================
    # 日期操作
    # ================================================================

    def set_date(
        self,
        date_str: str,
        label_text: str = "结束日期:",
    ) -> None:
        """
        设置报表参数面板中的日期选择器。

        Args:
            date_str: 日期字符串，格式 "YYYY-MM-DD"
            label_text: 日期标签文本，如 "开始日期:" / "结束日期:"
        """
        logger.info("设置日期 [%s] = %s", label_text, date_str)
        self.fr_fill_date_by_label(label_text, date_str)

    def set_end_date(self, date_str: str) -> None:
        """快捷设置结束日期。"""
        self.set_date(date_str, "结束日期:")

    def set_start_date(self, date_str: str) -> None:
        """快捷设置开始日期。"""
        self.set_date(date_str, "开始日期:")

    # ================================================================
    # 下拉复选框操作（产品型号、Group 等）
    # ================================================================

    def select_dropdown_options(
        self,
        options: list[str],
        label_text: str = "产品型号:",
    ) -> None:
        """
        在指定的下拉复选框中精准勾选特定选项。

        Args:
            options: 需要勾选的选项列表
            label_text: 下拉框的标签文本
        """
        if not options:
            logger.info("选项列表为空，跳过下拉框 [%s] 设置", label_text)
            return
        logger.info("设置下拉框 [%s] 勾选 %d 个选项", label_text, len(options))
        self.fr_dropdown_select_specific(label_text, options)

    def select_all_dropdown_options(self, label_text: str = "产品型号:") -> None:
        """将指定的下拉复选框设为「全选」状态。"""
        logger.info("设置下拉框 [%s] 为全选", label_text)
        self.fr_dropdown_select_all(label_text)

    # ================================================================
    # 查询与导出快捷操作
    # ================================================================

    def click_query_and_wait(
        self,
        wait_text: str | None = None,
        wait_timeout: int = 120000,
    ) -> None:
        """
        点击 [查询] 按钮并等待报表渲染完成。

        Args:
            wait_text: 可选的特征文本等待（如某个表头文字）
            wait_timeout: 等待超时（毫秒）
        """
        self.fr_click_query()
        if wait_text:
            self.fr_wait_for_specific_text(wait_text, timeout=wait_timeout)
        else:
            self.fr_wait_for_report_ready(timeout=wait_timeout)

    def export_excel(self) -> None:
        """触发帆软原样导出操作。"""
        logger.info("触发 Excel 原样导出...")
        self.fr_export_excel_original()

    # ================================================================
    # 调试辅助
    # ================================================================

    def pause_for_debug(self, message: str = "🛑 暂停，请检查浏览器状态") -> None:
        """在非 headless 模式下暂停，方便人工调试。"""
        logger.warning("%s。可在 Playwright 浏览器中手动操作后继续。", message)
        try:
            self.page.pause()
        except Exception:
            logger.info("pause() 不可用（headless 模式或无终端），跳过调试暂停。")
