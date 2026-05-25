"""
finereport_client.py: FineReport 报表客户端（RPA 方案）

【职责】
    封装 V3 良率报表的 RPA 下载能力，对外提供与旧版 REST API 方案一致的接口。

【架构变更】
    从 REST API 方案迁移至 Playwright RPA 方案：
    - 旧方案：login → acquire_session → submit_parameters → fetch_page → parse_html
    - 新方案：launch_browser → navigate → login → search_report → set_params → export

【红线】
    - download_daily_yield_report() 和 download_batch_yield_report() 签名保持不变
    - FineReportConnectionError / FineReportDownloadError / FineReportSessionError 异常类保持不变
    - 所有 FineReport 连接信息仍从 .env 文件读取
"""

from __future__ import annotations

import logging
import os
import re as _re
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from fr_web_automation.config import BrowserConfig, WebAutomationConfig
from shared_kernel.config import ConfigLoader
from yield_report.infrastructure.yield_download_service import (
    YieldDownloadService as _YieldDownloadService,
)

logger = logging.getLogger("FinereportClient")


# ================================================================
# 异常类（保持向后兼容）
# ================================================================


class FineReportConnectionError(Exception):
    """FineReport 服务器连接失败或配置错误。"""


class FineReportSessionError(Exception):
    """FineReport 会话异常（如 Token 过期、Session 无效）。"""


class FineReportDownloadError(Exception):
    """FineReport 报表下载失败（如参数错误、数据为空）。"""


# ================================================================
# 客户端
# ================================================================


class FinereportClient:
    """
    FineReport 报表客户端（RPA 方案）。

    封装了完整的帆软报表 RPA 下载流水线：
    1. 启动 Playwright 浏览器（首次调用时）
    2. 导航到门户主页并登录
    3. 搜索指定报表 → 设置筛选参数 → 导出 Excel
    4. 保存文件到指定目录

    线程安全：每个实例独立维护浏览器会话，不共享状态。
    """

    def __init__(self) -> None:
        # 从 .env 加载 FineReport 配置
        load_dotenv()

        # 绕过内网代理（必须）：将 FineReport 服务器地址加入 NO_PROXY
        host = os.getenv("FINEREPORT_HOST", "")
        host_domain = _re.sub(r"https?://", "", host).split(":")[0] if host else ""
        current_no_proxy = os.getenv("NO_PROXY", "")
        if host_domain and host_domain not in current_no_proxy:
            new_no_proxy = (
                f"{current_no_proxy},{host_domain}" if current_no_proxy else host_domain
            )
            os.environ["NO_PROXY"] = new_no_proxy
            logger.info("已将 %s 加入 NO_PROXY", host_domain)

        self._host: str = os.getenv("FINEREPORT_HOST", "").rstrip("/")
        self._username: str = os.getenv("FINEREPORT_USERNAME", "")
        self._password: str = os.getenv("FINEREPORT_PASSWORD", "")
        self._entry_uuid: str = os.getenv("FINEREPORT_ENTRY_UUID", "")

        # 验证必需配置
        missing = []
        if not self._host:
            missing.append("FINEREPORT_HOST")
        if not self._username:
            missing.append("FINEREPORT_USERNAME")
        if not self._password:
            missing.append("FINEREPORT_PASSWORD")
        if not self._entry_uuid:
            missing.append("FINEREPORT_ENTRY_UUID")
        if missing:
            raise FineReportConnectionError(
                f"FineReport 配置不完整，请在 .env 文件中设置: {', '.join(missing)}"
            )

        self._resources_dir: Path = self._resolve_resources_dir()

        # RPA 下载服务（懒加载）
        self._rpa_service: _YieldDownloadService | None = None
        self._rpa_download_dir: Path | None = None

    # ================================================================
    # 公共方法
    # ================================================================

    def download_daily_yield_report(
        self,
        end_date: str | date | None = None,
        product_models: list[str] | None = None,
        save_dir: str | Path | None = None,
    ) -> Path:
        """
        下载"V3良率及不良率By月周天汇总报表"。

        Args:
            end_date: 结束日期 (默认今天)
            product_models: 产品型号列表 (默认全部)
            save_dir: 保存目录 (默认 resources/)

        Returns:
            Path: 下载文件的完整路径

        Raises:
            FineReportDownloadError: 下载失败
        """
        save_dir = Path(save_dir) if save_dir else self._resources_dir
        end_date_str = self._normalize_date(end_date)

        service = self._get_rpa_service()
        return service.download_daily_yield(
            end_date=end_date_str,
            product_models=product_models,
            save_dir=save_dir,
        )

    def download_batch_yield_report(
        self,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        product_models: list[str] | None = None,
        save_dir: str | Path | None = None,
    ) -> Path:
        """
        下载"V3良率及不良率By批次汇总报表"。

        Args:
            start_date: 开始日期 (默认三个月前月初)
            end_date: 结束日期 (默认今天)
            product_models: 产品型号列表 (默认全部)
            save_dir: 保存目录 (默认 resources/)

        Returns:
            Path: 下载文件的完整路径

        Raises:
            FineReportDownloadError: 下载失败
        """
        save_dir = Path(save_dir) if save_dir else self._resources_dir
        start_date_str = self._normalize_date(start_date) if start_date else None
        end_date_str = self._normalize_date(end_date)

        service = self._get_rpa_service()
        return service.download_batch_yield(
            start_date=start_date_str,
            end_date=end_date_str,
            product_models=product_models,
            save_dir=save_dir,
        )

    # ================================================================
    # 内部方法：RPA 服务管理
    # ================================================================

    def _get_rpa_service(self) -> _YieldDownloadService:
        """获取或创建 RPA 下载服务（懒加载 + 单例复用）。"""
        if self._rpa_service is None:
            # 构建入口 URL，使用目录页面
            portal_url = (
                f"{self._host}/webroot/decision#directory"
            )

            # 配置 RPA 下载目录（使用临时子目录，避免污染 resources/）
            self._rpa_download_dir = self._resources_dir / ".rpa_downloads"
            self._rpa_download_dir.mkdir(parents=True, exist_ok=True)

            rpa_config = WebAutomationConfig(
                browser=BrowserConfig(
                    headless=False,
                    timeout=120000,
                    slow_mo=100,
                    channel="chrome",  # 使用系统 Chrome，避免下载捆绑 Chromium
                ),
                download_dir=str(self._rpa_download_dir),
            )

            self._rpa_service = _YieldDownloadService(
                config=rpa_config,
                portal_url=portal_url,
                username=self._username,
                password=self._password,
            )

        return self._rpa_service

    # ================================================================
    # 辅助方法
    # ================================================================

    @staticmethod
    def _resolve_resources_dir() -> Path:
        """解析 resources 目录路径。"""
        try:
            config_loader = ConfigLoader()
            app_config = config_loader.get()
            return Path(app_config.paths.resources_dir)
        except Exception:
            return Path("resources")

    @staticmethod
    def _normalize_date(d: str | date | None) -> str:
        """将日期参数统一为 "YYYY-MM-DD" 字符串。"""
        if d is None:
            return date.today().isoformat()
        if isinstance(d, date):
            return d.isoformat()
        return str(d)
