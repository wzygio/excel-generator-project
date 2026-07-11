"""
orchestrator.py: 数据获取编排器 (Application 层)

DataAcquisitionOrchestrator 是"数据获取层"的总控模块。
它串联了:
1. QueryParser (Core) - 自然语言解析
2. FinereportClient (Infrastructure) - FineReport 报表下载
3. LocalFileLoader (Infrastructure) - 本地/网络文件加载
4. Product Models (Infrastructure) - 产品型号提取

工作流:
    用户输入自然语言
        → QueryParser 解析为 ReportQueryRequest
        → 根据 report_type 分发到对应下载器/加载器
        → 返回执行结果 (成功/失败 + 文件路径)

使用方式:
    orchestrator = DataAcquisitionOrchestrator()
    result = orchestrator.process_user_query("帮我下载今天的V3良率报表")
    print(result)
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from shared_kernel.config import ConfigLoader
from shared_kernel.config_model import SourceFileConfig
from yield_report.core.business_time import (
    default_batch_start_date,
    effective_report_end_date,
)
from yield_report.core.query_parser import (
    QueryParser,
    QueryParserError,
    ReportQueryRequest,
    ReportType,
    build_report_type_meta,
)
from yield_report.infrastructure.finereport_client import (
    FinereportClient,
    FineReportConnectionError,
    FineReportDownloadError,
)
from yield_report.infrastructure.local_file_loader import (
    LocalFileLoader,
    LocalFileNotFoundError,
    NetworkFileCopyError,
)
from yield_report.infrastructure.logging_config import configure_yield_report_logging
from yield_report.infrastructure.product_models import (
    ProductModelExtractionError,
    extract_product_models,
)

logger = logging.getLogger(__name__)


@dataclass
class AcquisitionResult:
    """
    单个文件获取结果。

    Attributes:
        success: 是否成功
        file_path: 文件路径 (成功时)
        file_description: 文件描述
        error_message: 错误信息 (失败时)
    """

    success: bool
    file_description: str = ""
    file_path: Path | None = None
    error_message: str = ""


@dataclass
class UserQueryResult:
    """
    用户查询处理结果。

    Attributes:
        success: 是否全部成功
        parsed_request: 解析后的结构化请求
        results: 各文件的获取结果列表
        summary: 简短摘要
    """

    success: bool
    parsed_request: ReportQueryRequest
    results: list[AcquisitionResult] = field(default_factory=list)
    summary: str = ""


class DataAcquisitionOrchestrator:
    """
    数据获取编排器。

    协调自然语言解析和底层数据获取模块，对外暴露简洁的
    process_user_query() 接口。
    """

    def __init__(
        self,
        llm_provider: str | None = None,
        clock: Callable[[], datetime] | None = None,
        source_files: Mapping[str, SourceFileConfig] | None = None,
    ) -> None:
        """
        Args:
            llm_provider: LLM 供应商 ("deepseek" / "gemini")，默认从 config 读取
        """
        configure_yield_report_logging()
        catalog = source_files if source_files is not None else ConfigLoader().get().source_files
        self._source_files = dict(catalog)
        self._report_type_meta = build_report_type_meta(self._source_files)
        self._query_parser = QueryParser(
            provider=llm_provider,
            source_files=self._source_files,
        )
        self._clock = clock
        self._finereport_client: FinereportClient | None = None
        self._local_file_loader = LocalFileLoader(source_files=self._source_files)

    def _report_description(self, report_type: ReportType) -> str:
        return self._report_type_meta[report_type]["name"]

    # ================================================================
    # 公共接口
    # ================================================================

    def process_user_query(self, user_input: str) -> UserQueryResult:
        """
        处理用户的自然语言查询。

        完整工作流:
        1. LLM 解析自然语言 → ReportQueryRequest
        2. 根据 report_type 调度对应获取模块
        3. 收集所有结果并返回

        Args:
            user_input: 用户自然语言输入

        Returns:
            UserQueryResult: 包含解析结果和各文件获取结果
        """
        # Step 1: 解析自然语言
        try:
            request = self._query_parser.parse(user_input)
        except QueryParserError as e:
            logger.warning(
                "Data acquisition query parsing failed: %s",
                e,
                extra={"event": "failure", "purpose": "business"},
            )
            return UserQueryResult(
                success=False,
                parsed_request=ReportQueryRequest(user_intent="解析失败"),
                results=[
                    AcquisitionResult(
                        success=False,
                        file_description="查询解析",
                        error_message=f"无法理解您的查询: {e}",
                    )
                ],
                summary=f"❌ 查询解析失败: {e}",
            )

        return self.process_request(request)

    def process_request(self, request: ReportQueryRequest) -> UserQueryResult:
        """
        Process an already-structured report acquisition request.

        This is the Agent/Skill-friendly interface: Codex or the runtime can
        produce a `ReportQueryRequest` from a Spec and execute the stable
        acquisition workflow without forcing another natural-language parse.
        """
        logger.info(
            "Data acquisition request started: report_type=%s",
            request.report_type,
            extra={"event": "start", "purpose": "business"},
        )
        # Step 2: 根据 report_type 执行获取
        results: list[AcquisitionResult] = []

        if request.report_type == ReportType.DAILY_YIELD:
            results = self._acquire_daily_yield(request)
        elif request.report_type == ReportType.BATCH_YIELD:
            results = self._acquire_batch_yield(request)
        elif request.report_type == ReportType.CT_EXCEPTION:
            results = self._acquire_ct_exception()
        elif request.report_type == ReportType.TARGET_DECOMPOSITION:
            results = self._acquire_target_decomposition()
        elif request.report_type == ReportType.GAP_TEMPLATE:
            results = self._acquire_gap_template()
        else:
            # report_type 未指定或不确定 - 不能盲目下载所有文件，先搜索 FineReport。
            results = self._search_unknown_report(request)

        # Step 3: 汇总结果
        success_count = sum(1 for r in results if r.success)
        total_count = len(results)
        all_success = success_count == total_count

        if all_success:
            summary = f"✅ 成功获取 {success_count}/{total_count} 份文件"
        elif success_count > 0:
            summary = f"⚠️ 部分成功: {success_count}/{total_count} 份文件获取成功"
        else:
            summary = f"❌ 所有文件获取失败 ({total_count}/{total_count})"

        logger.log(
            logging.INFO if all_success else logging.WARNING if success_count else logging.ERROR,
            "Data acquisition request completed: success_count=%d total_count=%d",
            success_count,
            total_count,
            extra={
                "event": "success" if all_success else "failure",
                "purpose": "business",
            },
        )
        return UserQueryResult(
            success=all_success,
            parsed_request=request,
            results=results,
            summary=summary,
        )

    # ================================================================
    # 具体获取方法
    # ================================================================

    def _acquire_daily_yield(
        self,
        request: ReportQueryRequest,
    ) -> list[AcquisitionResult]:
        """获取月周天汇总报表。"""
        results: list[AcquisitionResult] = []
        description = self._report_description(ReportType.DAILY_YIELD)

        try:
            # 获取产品型号列表
            product_models = self._resolve_product_models(request.product_models)

            # 解析日期。上午十点前日度数据仍截止到昨日。
            end_date = request.end_date or effective_report_end_date(self._clock).isoformat()

            # 下载
            client = self._get_finereport_client()
            file_path = client.download_daily_yield_report(
                end_date=end_date,
                product_models=product_models,
                month_count=request.month_count,
            )
            results.append(
                AcquisitionResult(
                    success=True,
                    file_description=description,
                    file_path=file_path,
                )
            )
        except FineReportConnectionError as e:
            results.append(
                AcquisitionResult(
                    success=False,
                    file_description=description,
                    error_message=f"FineReport 连接失败: {e}",
                )
            )
        except FineReportDownloadError as e:
            results.append(
                AcquisitionResult(
                    success=False,
                    file_description=description,
                    error_message=f"下载失败: {e}",
                )
            )
        except ProductModelExtractionError as e:
            results.append(
                AcquisitionResult(
                    success=False,
                    file_description=description,
                    error_message=f"产品型号提取失败: {e}",
                )
            )
        except Exception as e:
            logger.exception("月周天汇总报表获取失败")
            results.append(
                AcquisitionResult(
                    success=False,
                    file_description=description,
                    error_message=f"获取失败: {e}",
                )
            )

        return results

    def _acquire_batch_yield(
        self,
        request: ReportQueryRequest,
    ) -> list[AcquisitionResult]:
        """获取批次汇总报表。"""
        results: list[AcquisitionResult] = []
        description = self._report_description(ReportType.BATCH_YIELD)

        try:
            # 获取产品型号列表
            product_models = self._resolve_product_models(request.product_models)

            # 批次良率默认查询最近 90 天；十点前结束日期仍为昨日。
            start_date = request.start_date or default_batch_start_date(self._clock).isoformat()
            end_date = request.end_date or effective_report_end_date(self._clock).isoformat()

            # 下载
            client = self._get_finereport_client()
            file_path = client.download_batch_yield_report(
                start_date=start_date,
                end_date=end_date,
                product_models=product_models,
            )
            results.append(
                AcquisitionResult(
                    success=True,
                    file_description=description,
                    file_path=file_path,
                )
            )
        except FineReportConnectionError as e:
            results.append(
                AcquisitionResult(
                    success=False,
                    file_description=description,
                    error_message=f"FineReport 连接失败: {e}",
                )
            )
        except FineReportDownloadError as e:
            results.append(
                AcquisitionResult(
                    success=False,
                    file_description=description,
                    error_message=f"下载失败: {e}",
                )
            )
        except ProductModelExtractionError as e:
            results.append(
                AcquisitionResult(
                    success=False,
                    file_description=description,
                    error_message=f"产品型号提取失败: {e}",
                )
            )
        except Exception as e:
            logger.exception("批次汇总报表获取失败")
            results.append(
                AcquisitionResult(
                    success=False,
                    file_description=description,
                    error_message=f"获取失败: {e}",
                )
            )

        return results

    def _acquire_ct_exception(self) -> list[AcquisitionResult]:
        """获取 CT 异常管理表。"""
        results: list[AcquisitionResult] = []
        description = self._report_description(ReportType.CT_EXCEPTION)

        try:
            file_path = self._local_file_loader.ensure_ct_exception_file()
            results.append(
                AcquisitionResult(
                    success=True,
                    file_description=description,
                    file_path=file_path,
                )
            )
        except (LocalFileNotFoundError, NetworkFileCopyError) as e:
            results.append(
                AcquisitionResult(
                    success=False,
                    file_description=description,
                    error_message=str(e),
                )
            )

        return results

    def _acquire_target_decomposition(self) -> list[AcquisitionResult]:
        """获取良率目标拆解表。"""
        results: list[AcquisitionResult] = []
        description = self._report_description(ReportType.TARGET_DECOMPOSITION)

        try:
            file_path = self._local_file_loader.ensure_target_decomposition_file()
            results.append(
                AcquisitionResult(
                    success=True,
                    file_description=description,
                    file_path=file_path,
                )
            )
        except LocalFileNotFoundError as e:
            results.append(
                AcquisitionResult(
                    success=False,
                    file_description=description,
                    error_message=str(e),
                )
            )

        return results

    def _acquire_gap_template(self) -> list[AcquisitionResult]:
        """获取 Gap 分析模板。"""
        results: list[AcquisitionResult] = []
        description = self._report_description(ReportType.GAP_TEMPLATE)

        try:
            file_path = self._local_file_loader.ensure_gap_template_file()
            results.append(
                AcquisitionResult(
                    success=True,
                    file_description=description,
                    file_path=file_path,
                )
            )
        except LocalFileNotFoundError as e:
            results.append(
                AcquisitionResult(
                    success=False,
                    file_description=description,
                    error_message=str(e),
                )
            )

        return results

    def _acquire_all_files(self) -> list[AcquisitionResult]:
        """
        获取所有 5 份源表文件。

        当用户未明确指定报表类型时，尝试获取所有文件。
        """
        all_results: list[AcquisitionResult] = []
        daily_description = self._report_description(ReportType.DAILY_YIELD)
        batch_description = self._report_description(ReportType.BATCH_YIELD)

        # FineReport 报表
        try:
            client = self._get_finereport_client()
            product_models = self._resolve_product_models(None)
            today = effective_report_end_date(self._clock).isoformat()

            fr_results_daily = client.download_daily_yield_report(
                end_date=today,
                product_models=product_models,
            )
            all_results.append(
                AcquisitionResult(
                    success=True,
                    file_description=daily_description,
                    file_path=fr_results_daily,
                )
            )
        except Exception as e:
            all_results.append(
                AcquisitionResult(
                    success=False,
                    file_description=daily_description,
                    error_message=str(e),
                )
            )

        try:
            client = self._get_finereport_client()
            product_models = self._resolve_product_models(None)
            start_date = default_batch_start_date(self._clock).isoformat()
            today = effective_report_end_date(self._clock).isoformat()

            fr_results_batch = client.download_batch_yield_report(
                start_date=start_date,
                end_date=today,
                product_models=product_models,
            )
            all_results.append(
                AcquisitionResult(
                    success=True,
                    file_description=batch_description,
                    file_path=fr_results_batch,
                )
            )
        except Exception as e:
            all_results.append(
                AcquisitionResult(
                    success=False,
                    file_description=batch_description,
                    error_message=str(e),
                )
            )

        # 本地文件
        all_results.extend(self._acquire_ct_exception())
        all_results.extend(self._acquire_target_decomposition())
        all_results.extend(self._acquire_gap_template())

        return all_results

    def _search_unknown_report(self, request: ReportQueryRequest) -> list[AcquisitionResult]:
        """Search FineReport when the report type cannot be determined."""
        keyword = _extract_report_search_keyword(request)
        if not keyword:
            return [
                AcquisitionResult(
                    success=False,
                    file_description="FineReport 报表搜索",
                    error_message="无法判断报表类型，且未能从需求中提取可用于帆软搜索的关键词。",
                )
            ]

        try:
            client = self._get_finereport_client()
            matches = client.search_reports(keyword)
        except (FineReportConnectionError, FineReportDownloadError) as e:
            return [
                AcquisitionResult(
                    success=False,
                    file_description="FineReport 报表搜索",
                    error_message=f"无法判断报表类型；已尝试用关键词「{keyword}」搜索帆软，但搜索失败: {e}",
                )
            ]
        except Exception as e:
            logger.exception("FineReport 报表搜索失败")
            return [
                AcquisitionResult(
                    success=False,
                    file_description="FineReport 报表搜索",
                    error_message=f"无法判断报表类型；已尝试用关键词「{keyword}」搜索帆软，但搜索失败: {e}",
                )
            ]

        if matches:
            preview = "；".join(matches[:5])
            message = (
                f"无法判断要下载的具体报表；已用关键词「{keyword}」搜索帆软，"
                f"候选结果: {preview}。请指定其中一个报表名称后重试。"
            )
        else:
            message = f"无法判断要下载的具体报表；已用关键词「{keyword}」搜索帆软，但未找到候选结果。"
        return [
            AcquisitionResult(
                success=False,
                file_description="FineReport 报表搜索",
                error_message=message,
            )
        ]

    # ================================================================
    # 辅助方法
    # ================================================================

    def _get_finereport_client(self) -> FinereportClient:
        """获取或创建 FineReport 客户端（懒加载）。"""
        if self._finereport_client is None:
            self._finereport_client = FinereportClient()
        return self._finereport_client

    @staticmethod
    def _resolve_product_models(
        user_models: list[str] | None,
    ) -> list[str] | None:
        """
        解析产品型号列表。

        如果用户在查询中指定了型号，直接使用。
        如果用户说"所有型号"或未指定，尝试从 spotfire.xlsx 自动读取。
        """
        if user_models is not None:
            return user_models

        try:
            models = extract_product_models()
            if models:
                logger.info("自动从 spotfire.xlsx 读取到 %d 个产品型号", len(models))
                return models
        except Exception as e:
            logger.warning("自动读取产品型号失败: %s", e)

        return None


def _extract_report_search_keyword(request: ReportQueryRequest) -> str:
    """Choose one exact keyword for FineReport's non-fuzzy search box."""
    text_parts = [request.user_intent or "", request.uncertainty_notes or ""]
    if request.product_models:
        text_parts.extend(request.product_models)
    text = " ".join(part for part in text_parts if part).strip()
    if not text:
        return ""

    for keyword in ["批次", "月周天", "CT异常", "异常", "目标", "拆解", "Gap", "良率"]:
        if keyword.lower() in text.lower():
            return keyword

    stopwords = {
        "查询",
        "下载",
        "报表",
        "数据",
        "帮我",
        "用于",
        "分析",
        "无法",
        "判断",
        "具体",
        "用户",
        "需求",
    }
    for token in re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]{2,}", text):
        if token not in stopwords:
            return token
    return ""
