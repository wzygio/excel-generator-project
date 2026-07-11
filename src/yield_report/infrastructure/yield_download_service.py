"""
yield_download_service.py: 良率报表下载业务编排服务

【职责】
    继承 DownloadService，编排 V3 良率报表（月周天汇总/批次汇总）的
    完整 RPA 下载管线：启动浏览器 → 登录 → 导航 → 参数设置 → 导出 → 关闭。

【设计原则】
    - 不包含 web_automation 通用逻辑（保持该包的通用性）
    - 报表名、标签、目录和超时只从经过 Pydantic 校验的配置注入
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from fr_web_automation.application.download_service import DownloadService
from fr_web_automation.config import WebAutomationConfig

from shared_kernel.config_model import FineReportDownloadConfig, SourceFileConfig
from yield_report.core.business_time import (
    default_batch_start_date,
    effective_report_end_date,
)
from yield_report.infrastructure.yield_portal_adapter import (
    YieldPortalAdapter,
)

logger = logging.getLogger(__name__)


class YieldDownloadService(DownloadService):
    """
    良率报表下载业务编排服务。

    提供两个核心方法：
    - download_daily_yield(): 下载月周天汇总报表
    - download_batch_yield(): 下载批次汇总报表

    浏览器生命周期管理：
    - 首次调用时启动浏览器并登录
    - 后续调用复用同一会话
    - 调用 shutdown() 可显式关闭浏览器
    """

    def __init__(
        self,
        config: WebAutomationConfig,
        portal_url: str,
        username: str,
        password: str,
        settings: FineReportDownloadConfig,
        source_files: Mapping[str, SourceFileConfig],
    ) -> None:
        """
        Args:
            config: WebAutomation 配置（浏览器、下载目录等）
            portal_url: FineReport 门户入口 URL
            username: 登录用户名
            password: 登录密码
        """
        super().__init__(config)
        self._portal_url = portal_url
        self._username = username
        self._password = password
        self._settings = settings
        self._source_files = dict(source_files)
        self._require_source("daily_yield")
        self._require_source("batch_yield")
        # 类型标注：初始化时为 None，_ensure_browser_ready() 后保证非空
        self._portal_adapter: YieldPortalAdapter = None  # type: ignore[assignment]
        self._browser_initialized = False

    # ================================================================
    # 公共下载方法
    # ================================================================

    def download_daily_yield(
        self,
        end_date: str | None = None,
        product_models: list[str] | None = None,
        month_count: int | None = None,
        save_dir: Path | None = None,
    ) -> Path:
        """
        下载「月周天汇总报表」。

        Args:
            end_date: 结束日期，格式 "YYYY-MM-DD"（默认今天）
            product_models: 产品型号列表（默认全部型号）
            save_dir: 保存目录（默认下载目录）

        Returns:
            下载文件的完整路径
        """
        end_date = end_date or effective_report_end_date().isoformat()
        source = self._require_source("daily_yield")
        save_path = self._resolve_save_path(save_dir, source.filename)

        logger.info(">>> 开始下载月周天汇总报表 <<<")
        logger.info("  结束日期: %s", end_date)

        self._ensure_browser_ready()
        adapter = self._get_adapter()

        try:
            self._navigate_to_report(
                source.description,
                report_path=self._settings.report_directory,
            )

            # 设置参数
            adapter.set_date(end_date, self._settings.labels.end_date)
            if month_count is not None:
                try:
                    adapter.set_text_parameter(
                        str(month_count),
                        self._settings.labels.month_count,
                    )
                except Exception:
                    logger.warning('月数字段不可用（该报表可能不含此参数），跳过月数设置')
            self._handle_product_models(product_models)

            # 查询并导出
            self._query_and_export(
                file_name=source.filename,
                save_path=save_path,
            )

            logger.info("✅ 月周天报表下载完成: %s", save_path)
            return save_path

        except Exception as e:
            self._capture_debug_artifacts("daily_yield_failed")
            logger.error("❌ 月周天报表下载失败: %s", e)
            self._get_adapter().reset_search_state()
            raise

    def download_batch_yield(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        product_models: list[str] | None = None,
        save_dir: Path | None = None,
    ) -> Path:
        """
        下载「批次汇总报表」。

        Args:
            start_date: 开始日期，格式 "YYYY-MM-DD"（默认三个月前月初）
            end_date: 结束日期，格式 "YYYY-MM-DD"（默认今天）
            product_models: 产品型号列表（默认全部型号）
            save_dir: 保存目录（默认下载目录）

        Returns:
            下载文件的完整路径
        """
        start_date = start_date or self._default_start_date()
        end_date = end_date or effective_report_end_date().isoformat()
        source = self._require_source("batch_yield")
        save_path = self._resolve_save_path(save_dir, source.filename)

        logger.info(">>> 开始下载批次汇总报表 <<<")
        logger.info("  开始日期: %s  结束日期: %s", start_date, end_date)

        self._ensure_browser_ready()
        adapter = self._get_adapter()

        try:
            self._navigate_to_report(
                source.description,
                report_path=self._settings.report_directory,
            )

            # 设置参数
            adapter.set_date(start_date, self._settings.labels.start_date)
            adapter.set_date(end_date, self._settings.labels.end_date)
            self._handle_product_models(product_models)

            # 查询并导出
            self._query_and_export(
                file_name=source.filename,
                save_path=save_path,
            )

            logger.info("✅ 批次报表下载完成: %s", save_path)
            return save_path

        except Exception as e:
            self._capture_debug_artifacts("batch_yield_failed")
            logger.error("❌ 批次报表下载失败: %s", e)
            self._get_adapter().reset_search_state()
            raise

    def shutdown(self) -> None:
        """
        关闭浏览器，释放资源。

        在非 headless 模式下，浏览器保持开启以便检查。
        """
        logger.info("正在关闭 RPA 下载服务...")
        self._handle_shutdown()
        self._browser_initialized = False

    def search_reports(self, keyword: str, limit: int = 10) -> list[str]:
        """Search the FineReport portal when a report name cannot be inferred."""
        self._ensure_browser_ready()
        return self._get_adapter().search_report_titles(keyword, limit=limit)

    # ================================================================
    # 内部方法：浏览器生命周期
    # ================================================================

    def _ensure_browser_ready(self) -> None:
        """
        确保浏览器已启动并完成登录。

        首次调用时启动浏览器并登录，后续调用复用同一会话。
        """
        if self._browser_initialized:
            logger.debug("浏览器会话已就绪，直接复用。")
            return

        logger.info("启动浏览器并执行登录...")
        self.page = self.start_engine()
        self._portal_adapter = YieldPortalAdapter(
            self.page,
            timeout=self._settings.browser.timeout_ms,
        )

        # 导航到门户首页
        adapter = self._portal_adapter
        adapter.navigate_to_home(self._portal_url)

        # 执行登录
        adapter.login(self._username, self._password)

        self._browser_initialized = True
        logger.info("✅ 浏览器就绪，已登录门户。")

    def _get_adapter(self) -> YieldPortalAdapter:
        """获取 PortalAdapter 实例（类型安全的 getter）。"""
        assert self._portal_adapter is not None, (
            "浏览器未初始化，请先调用 _ensure_browser_ready()"
        )
        return self._portal_adapter

    # ================================================================
    # 内部方法：报表导航
    # ================================================================

    def _navigate_to_report(self, report_name: str, report_path: str = "") -> None:
        """
        搜索并进入指定报表。

        先重置搜索状态，再执行搜索导航，确保每次导航都是干净的。
        导航后等待参数面板的 iframe 完全加载，确保日期/下拉框等 UI 组件可用。
        """
        logger.info("搜索并进入报表: %s | 路径: %s", report_name, report_path or "未指定")
        adapter = self._get_adapter()
        adapter.reset_search_state()
        time.sleep(0.5)
        adapter.search_and_enter_report(report_name, report_path=report_path)
        # 显式等待参数面板加载，而非盲等
        adapter.wait_for_report_frame(timeout=self._settings.browser.timeout_ms)

    # ================================================================
    # 内部方法：参数设置
    # ================================================================

    def _handle_product_models(
        self,
        product_models: list[str] | None = None,
    ) -> None:
        """
        处理产品型号参数设置。

        Args:
            product_models: 产品型号列表，None 表示全选
        """
        adapter = self._get_adapter()
        if product_models:
            logger.info("设置产品型号（%d 个）...", len(product_models))
            adapter.select_dropdown_options(
                product_models,
                label_text=self._settings.labels.product_model,
            )
        else:
            logger.info("未指定产品型号，执行全选...")
            adapter.select_all_dropdown_options(
                label_text=self._settings.labels.product_model,
            )

    # ================================================================
    # 内部方法：查询与导出
    # ================================================================

    def _query_and_export(
        self,
        file_name: str,
        save_path: Path,
    ) -> None:
        """
        执行「查询 → 等待渲染 → 导出 → 保存文件」管线。

        Args:
            file_name: 导出的文件名（用于下载监听匹配）
            save_path: 最终保存路径
        """
        adapter = self._get_adapter()

        # 1. 点击查询并等待渲染
        adapter.click_query_and_wait(
            wait_timeout=self._settings.report_wait_timeout_ms,
        )

        # 2. 执行导出并保存
        self.perform_download_action(
            action_callable=adapter.export_excel,
            file_name=file_name,
        )

        # 3. 将下载的文件移动到目标路径
        downloaded_file = self.download_dir / file_name
        if downloaded_file.exists():
            if save_path != downloaded_file:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                if save_path.exists():
                    save_path.unlink()
                downloaded_file.rename(save_path)
                logger.info("文件已移动到: %s", save_path)
        else:
            if not save_path.exists():
                logger.warning(
                    "未找到下载文件: %s，可能在 download_dir 中查找...",
                    downloaded_file,
                )

    # ================================================================
    # 辅助方法
    # ================================================================

    def _require_source(self, alias: str) -> SourceFileConfig:
        source = self._source_files.get(alias)
        if source is None:
            raise ValueError(f"source_files.{alias} is not configured")
        if not source.description.strip():
            raise ValueError(f"source_files.{alias}.description is not configured")
        if not source.filename.strip():
            raise ValueError(f"source_files.{alias}.filename is not configured")
        return source

    def _capture_debug_artifacts(self, name: str) -> None:
        """保存 RPA 失败时的页面截图和可见 iframe 文本，便于定位帆软页面状态。"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_root = _find_output_root(self.download_dir)
            screenshot_dir = output_root / "diagnostics" / "rpa" / "screenshots"
            console_dir = output_root / "diagnostics" / "rpa" / "console"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            console_dir.mkdir(parents=True, exist_ok=True)

            screenshot_path = screenshot_dir / f"{timestamp}_{name}.png"
            text_path = console_dir / f"{timestamp}_{name}.txt"

            adapter = self._get_adapter()
            adapter.page.screenshot(path=str(screenshot_path), full_page=True)

            lines = [f"url={adapter.page.url}", ""]
            for index, frame in enumerate(adapter.page.frames):
                try:
                    text = frame.locator("body").inner_text(timeout=1000)
                except Exception as exc:
                    text = f"<无法读取 frame 文本: {exc}>"
                lines.append(f"--- frame {index}: {frame.url} ---")
                lines.append(text[:5000])
                lines.append("")

            text_path.write_text("\n".join(lines), encoding="utf-8")
            logger.info("RPA 调试文件已保存: %s, %s", screenshot_path, text_path)
        except Exception as exc:
            logger.warning("保存 RPA 调试文件失败: %s", exc)

    def _resolve_save_path(
        self,
        save_dir: Path | None,
        filename: str,
    ) -> Path:
        """解析保存路径。"""
        if save_dir:
            return Path(save_dir) / filename
        return self.download_dir / filename

    @staticmethod
    def _default_start_date() -> str:
        """默认开始日期：今天往前 90 天。"""
        return default_batch_start_date().isoformat()


def _find_output_root(path: Path) -> Path:
    """Find the nearest output root for runtime diagnostics."""
    resolved = Path(path).resolve()
    for candidate in [resolved, *resolved.parents]:
        if candidate.name == "output":
            return candidate
    return resolved.parent
