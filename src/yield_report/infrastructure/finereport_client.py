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

from yield_report.shared_kernel.config import ConfigLoader
from yield_report.shared_kernel.config_model import AppConfig
from yield_report.core.business_time import (
    default_batch_start_date,
    effective_report_end_date,
)
from yield_report.infrastructure.file_decryption import (
    FileDecryptionError,
    decrypt_excel_file,
)
from yield_report.infrastructure.yield_download_service import (
    YieldDownloadService as _YieldDownloadService,
)

logger = logging.getLogger(__name__)
MAX_FILTER_SUFFIX_LENGTH = 120
DECRYPTED_WORKBOOKS_OUTPUT = Path("artifacts") / "workbooks" / "decrypted"
FINEREPORT_RAW_DOWNLOADS_OUTPUT = Path("downloads") / "raw" / "finereport"


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

    def __init__(self, app_config: AppConfig | None = None) -> None:
        # 从 .env 加载 FineReport 配置
        load_dotenv()
        app_config = app_config or ConfigLoader().get()

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

        self._resources_dir = Path(app_config.paths.resources_dir)
        self._output_dir = Path(app_config.paths.output_dir)
        self._download_settings = app_config.report_download.finereport
        self._source_files = dict(app_config.source_files)

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
        month_count: int | None = None,
        save_dir: str | Path | None = None,
    ) -> Path:
        """
        下载配置目录中的日度良率源报表。

        Args:
            end_date: 结束日期 (默认今天)
            product_models: 产品型号列表 (默认全部)
            save_dir: 保存目录 (默认 output/downloads/raw/finereport/)

        Returns:
            Path: 下载文件的完整路径

        Raises:
            FineReportDownloadError: 下载失败
        """
        save_dir = self._resolve_report_download_dir(save_dir)
        end_date_str = self._normalize_date(end_date)

        service = self._get_rpa_service()
        downloaded_path = service.download_daily_yield(
            end_date=end_date_str,
            product_models=product_models,
            month_count=month_count,
            save_dir=save_dir,
        )
        filters = {
            "结束日期": end_date_str,
            "产品型号": self._format_product_models(product_models),
        }
        if month_count is not None:
            filters["月数"] = str(month_count)
        filtered_path = self._rename_with_filter_suffix(downloaded_path, filters=filters)
        return self._decrypt_downloaded_file(filtered_path)

    def download_batch_yield_report(
        self,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        product_models: list[str] | None = None,
        save_dir: str | Path | None = None,
    ) -> Path:
        """
        下载配置目录中的批次良率源报表。

        Args:
            start_date: 开始日期 (默认三个月前月初)
            end_date: 结束日期 (默认今天)
            product_models: 产品型号列表 (默认全部)
            save_dir: 保存目录 (默认 output/downloads/raw/finereport/)

        Returns:
            Path: 下载文件的完整路径

        Raises:
            FineReportDownloadError: 下载失败
        """
        save_dir = self._resolve_report_download_dir(save_dir)
        start_date_str = (
            self._normalize_date(start_date)
            if start_date
            else self._default_batch_start_date()
        )
        end_date_str = self._normalize_date(end_date)

        service = self._get_rpa_service()
        downloaded_path = service.download_batch_yield(
            start_date=start_date_str,
            end_date=end_date_str,
            product_models=product_models,
            save_dir=save_dir,
        )
        filtered_path = self._rename_with_filter_suffix(
            downloaded_path,
            filters={
                "开始日期": start_date_str,
                "结束日期": end_date_str,
                "产品型号": self._format_product_models(product_models),
            },
        )
        return self._decrypt_downloaded_file(filtered_path)

    def search_reports(self, keyword: str, limit: int = 10) -> list[str]:
        """Search FineReport portal report titles/snippets by one exact keyword."""
        try:
            return self._get_rpa_service().search_reports(keyword, limit=limit)
        except Exception as exc:
            raise FineReportDownloadError(f"FineReport 报表搜索失败: {exc}") from exc

    # ================================================================
    # 内部方法：RPA 服务管理
    # ================================================================

    def _get_rpa_service(self) -> _YieldDownloadService:
        """获取或创建 RPA 下载服务（懒加载 + 单例复用）。"""
        if self._rpa_service is None:
            # 构建入口 URL，使用目录页面
            portal_url = f"{self._host}/webroot/decision#directory"

            # 配置 RPA 下载目录（生成物统一进入 output/）
            self._rpa_download_dir = self._output_dir / FINEREPORT_RAW_DOWNLOADS_OUTPUT
            self._rpa_download_dir.mkdir(parents=True, exist_ok=True)

            rpa_config = WebAutomationConfig(
                browser=BrowserConfig(
                    headless=self._download_settings.browser.headless,
                    timeout=self._download_settings.browser.timeout_ms,
                    slow_mo=self._download_settings.browser.slow_mo_ms,
                    channel=self._download_settings.browser.channel or None,
                ),
                download_dir=str(self._rpa_download_dir),
            )

            self._rpa_service = _YieldDownloadService(
                config=rpa_config,
                portal_url=portal_url,
                username=self._username,
                password=self._password,
                settings=self._download_settings,
                source_files=self._source_files,
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
    def _resolve_output_dir() -> Path:
        """解析 output 目录路径。"""
        try:
            config_loader = ConfigLoader()
            app_config = config_loader.get()
            return Path(app_config.paths.output_dir)
        except Exception:
            return Path("output")

    def _resolve_report_download_dir(self, save_dir: str | Path | None) -> Path:
        """解析原始报表下载保存目录。"""
        directory = Path(save_dir) if save_dir else self._output_dir / FINEREPORT_RAW_DOWNLOADS_OUTPUT
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @staticmethod
    def _normalize_date(d: str | date | None) -> str:
        """将日期参数统一为 "YYYY-MM-DD" 字符串。"""
        if d is None:
            return effective_report_end_date().isoformat()
        if isinstance(d, date):
            return d.isoformat()
        return str(d)

    @staticmethod
    def _default_batch_start_date() -> str:
        """批次报表默认开始日期：今天往前 90 天。"""
        return default_batch_start_date().isoformat()

    @staticmethod
    def _format_product_models(product_models: list[str] | None) -> str:
        """将产品型号列表压缩为适合文件名阅读的筛选值。"""
        if not product_models:
            return "全部"

        cleaned_models = [str(model).strip() for model in product_models if str(model).strip()]
        if not cleaned_models:
            return "全部"

        visible_models = cleaned_models[:5]
        suffix = "+".join(visible_models)
        if len(cleaned_models) > len(visible_models):
            suffix = f"{suffix}+等{len(cleaned_models)}项"
        return suffix

    @classmethod
    def _rename_with_filter_suffix(
        cls,
        file_path: Path,
        filters: dict[str, str],
    ) -> Path:
        """在下载文件名后追加筛选条件信息，并返回重命名后的路径。"""
        if not file_path.exists():
            logger.warning("待重命名的报表文件不存在: %s", file_path)
            return file_path

        suffix = "_".join(
            cls._safe_filename_part(f"{key}{value}")
            for key, value in filters.items()
            if value
        )
        suffix = suffix[:MAX_FILTER_SUFFIX_LENGTH].rstrip("._-")
        if not suffix:
            return file_path

        target_path = file_path.with_name(f"{file_path.stem}_{suffix}{file_path.suffix}")
        if target_path == file_path:
            return file_path

        if target_path.exists():
            target_path.unlink()
        file_path.rename(target_path)
        logger.info("已追加筛选条件到报表文件名: %s", target_path)
        return target_path

    def _decrypt_downloaded_file(self, file_path: Path) -> Path:
        """将下载文件解密到 output/artifacts/workbooks/decrypted，并返回解密后的路径。"""
        output_dir = self._output_dir / DECRYPTED_WORKBOOKS_OUTPUT
        try:
            return decrypt_excel_file(file_path, output_dir)
        except FileDecryptionError as exc:
            raise FineReportDownloadError(f"报表已下载但自动解密失败: {exc}") from exc

    @staticmethod
    def _safe_filename_part(value: str) -> str:
        """清理 Windows 文件名非法字符，保留可读的业务信息。"""
        safe_value = _re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
        safe_value = _re.sub(r"\s+", "", safe_value)
        return safe_value.strip("._ ") or "未指定"
