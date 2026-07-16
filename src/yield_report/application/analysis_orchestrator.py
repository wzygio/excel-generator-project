"""Application orchestrator for module 2: data analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yield_report.core.analysis_query_parser import (
    AnalysisQueryParser,
    AnalysisQueryParserError,
    AnalysisQueryRequest,
    build_heuristic_analysis_request,
)
from yield_report.core.analysis_selector import (
    AnalysisStrategy,
    AnalysisStrategySelector,
    StrategyDecision,
)
from yield_report.infrastructure.analysis_file_resolver import (
    AnalysisFileResolveError,
    AnalysisFileResolver,
    ResolvedAnalysisFile,
)
from yield_report.infrastructure.analysis_memory import (
    AnalysisMemoryCandidate,
    AnalysisMemoryRecord,
    AnalysisMemoryStore,
)
from yield_report.infrastructure.code_executor import CodeExecutor
from yield_report.infrastructure.code_generator import CodeGenerator, extract_schema
from yield_report.infrastructure.ct_yield_trend_analyzer import (
    CtYieldTrendAnalysisError,
    CtYieldTrendAnalyzer,
)
from yield_report.infrastructure.daily_yield_trend_analyzer import (
    DailyYieldTrendAnalysisError,
    DailyYieldTrendAnalyzer,
)
from yield_report.infrastructure.logging_config import configure_yield_report_logging

logger = logging.getLogger(__name__)


@dataclass
class AnalysisWorkflowStep:
    """One observable workflow step for UI diagnostics."""

    name: str
    status: str
    detail: str


@dataclass
class AnalysisResult:
    """Structured result returned by the data-analysis workflow."""

    success: bool
    strategy_used: AnalysisStrategy | None = None
    strategy_decision: StrategyDecision | None = None
    result_text: str = ""
    schema: str = ""
    error_message: str = ""
    parsed_request: AnalysisQueryRequest | None = None
    source_file_path: Path | None = None
    memory_record_id: str | None = None
    memory_candidates: list[AnalysisMemoryCandidate] = field(default_factory=list)
    workflow_steps: list[AnalysisWorkflowStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    goal_alignment: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        if not self.success:
            return f"❌ 分析失败: {self.error_message}"

        lines = [
            "✅ 分析完成",
            f"   策略: {self.strategy_used or 'N/A'}",
            f"   判定理由: {self.strategy_decision.reasoning if self.strategy_decision else 'N/A'}",
            f"   数据文件: {self.source_file_path or 'N/A'}",
            f"   结果长度: {len(self.result_text)} 字符",
        ]
        if self.memory_record_id:
            lines.append(f"   待确认记忆: {self.memory_record_id}")
        return "\n".join(lines)


LLM_DIRECT_ANALYSIS_PROMPT = """你是专业的良率数据分析师。请根据数据表结构和用户需求直接完成分析。

要求:
1. 先理解数据结构，识别关键字段。
2. 围绕用户需求给出针对性分析。
3. 使用中文输出，结构清晰。
4. 数据不足时要明确说明限制。

输出格式:
- **数据概览**:
- **分析过程**:
- **核心发现**:
- **建议**:
"""


class AnalysisOrchestrator:
    """Coordinate parsing, file resolution, strategy selection, and execution."""

    def __init__(
        self,
        llm_provider: str | None = None,
        resources_dir: Path | None = None,
        query_parser: AnalysisQueryParser | None = None,
        file_resolver: AnalysisFileResolver | None = None,
        memory_store: AnalysisMemoryStore | None = None,
        selector: AnalysisStrategySelector | None = None,
        code_generator: CodeGenerator | None = None,
        code_executor: CodeExecutor | None = None,
        ct_trend_analyzer: CtYieldTrendAnalyzer | None = None,
        daily_yield_trend_analyzer: DailyYieldTrendAnalyzer | None = None,
    ) -> None:
        configure_yield_report_logging()
        self._llm_provider = llm_provider or "deepseek"
        self._query_parser = query_parser or AnalysisQueryParser(provider=self._llm_provider)
        self._memory_store = memory_store or AnalysisMemoryStore()
        self._file_resolver = file_resolver or AnalysisFileResolver(resources_dir=resources_dir)
        self._selector = selector or AnalysisStrategySelector(provider=self._llm_provider)
        self._code_generator = code_generator or CodeGenerator()
        self._code_executor = code_executor or CodeExecutor()
        self._ct_trend_analyzer = ct_trend_analyzer or CtYieldTrendAnalyzer()
        self._daily_yield_trend_analyzer = (
            daily_yield_trend_analyzer or DailyYieldTrendAnalyzer()
        )

    def analyze(
        self,
        user_query: str,
        file_path: Path | None = None,
        file_name: str | None = None,
    ) -> AnalysisResult:
        """Run the complete module-2 analysis workflow."""
        workflow_steps: list[AnalysisWorkflowStep] = []
        try:
            parsed_request = self._query_parser.parse(
                user_query,
                provider=self._llm_provider,
            )
            workflow_steps.append(
                AnalysisWorkflowStep(
                    name="需求解析",
                    status="success",
                    detail=_describe_request(parsed_request),
                )
            )
        except AnalysisQueryParserError as exc:
            parsed_request = build_heuristic_analysis_request(user_query)
            if parsed_request is not None:
                workflow_steps.append(
                    AnalysisWorkflowStep(
                        name="需求解析",
                        status="warning",
                        detail=f"LLM解析失败，已使用启发式解析兜底: {_describe_request(parsed_request)}",
                    )
                )
            elif file_path is not None or file_name is not None:
                logger.warning("Analysis query parsing failed; continuing with explicit file: %s", exc)
                parsed_request = AnalysisQueryRequest(
                    user_intent=user_query,
                    uncertainty_notes=f"需求解析失败，已使用显式文件继续: {exc}",
                )
                workflow_steps.append(
                    AnalysisWorkflowStep(
                        name="需求解析",
                        status="warning",
                        detail=f"需求解析失败，使用显式文件继续: {exc}",
                    )
                )
            else:
                workflow_steps.append(
                    AnalysisWorkflowStep(name="需求解析", status="failed", detail=str(exc))
                )
                return AnalysisResult(
                    success=False,
                    workflow_steps=workflow_steps,
                    error_message=f"需求解析失败: {exc}",
                )

        memory_candidates = self._memory_store.find_candidates(parsed_request)
        if memory_candidates:
            workflow_steps.append(
                AnalysisWorkflowStep(
                    name="Agent-Memory",
                    status="success",
                    detail=f"命中 {len(memory_candidates)} 条已确认记忆，优先用于文件匹配。",
                )
            )
        else:
            workflow_steps.append(
                AnalysisWorkflowStep(
                    name="Agent-Memory",
                    status="success",
                    detail="未命中已确认记忆，进入本地文件扫描。",
                )
            )

        try:
            resolved_file = self._file_resolver.resolve(
                request=parsed_request,
                user_query=user_query,
                file_path=file_path,
                file_name=file_name,
                memory_candidates=memory_candidates,
            )
        except AnalysisFileResolveError as exc:
            workflow_steps.append(
                AnalysisWorkflowStep(name="文件扫描/下载/解密", status="failed", detail=str(exc))
            )
            return AnalysisResult(
                success=False,
                parsed_request=parsed_request,
                memory_candidates=memory_candidates,
                workflow_steps=workflow_steps,
                error_message=f"数据文件定位失败: {exc}",
            )

        logger.info("Analysis source resolved: %s (%s)", resolved_file.path, resolved_file.source)
        workflow_steps.append(
            AnalysisWorkflowStep(
                name="文件扫描/下载/解密",
                status="success",
                detail=(
                    f"source={resolved_file.source}; file={resolved_file.path}; "
                    f"decrypted={resolved_file.was_decrypted}"
                ),
            )
        )

        try:
            schema = extract_schema(resolved_file.path)
        except Exception as exc:
            workflow_steps.append(
                AnalysisWorkflowStep(name="Schema提取", status="failed", detail=str(exc))
            )
            return AnalysisResult(
                success=False,
                parsed_request=parsed_request,
                source_file_path=resolved_file.path,
                memory_candidates=memory_candidates,
                workflow_steps=workflow_steps,
                error_message=f"提取数据表 Schema 失败: {exc}",
            )
        workflow_steps.append(
            AnalysisWorkflowStep(
                name="Schema提取",
                status="success",
                detail=f"Schema 长度 {len(schema)} 字符。",
            )
        )

        try:
            decision = self._selector.decide(
                user_query=user_query,
                schema=schema,
                provider=self._llm_provider,
            )
        except Exception as exc:
            if not self._can_run_ct_trend(user_query, parsed_request) and not self._can_run_daily_yield_trend(
                user_query, parsed_request
            ):
                workflow_steps.append(
                    AnalysisWorkflowStep(name="分析策略判定", status="failed", detail=str(exc))
                )
                return AnalysisResult(
                    success=False,
                    parsed_request=parsed_request,
                    source_file_path=resolved_file.path,
                    memory_candidates=memory_candidates,
                    workflow_steps=workflow_steps,
                    schema=schema,
                    error_message=f"分析策略判定失败: {exc}",
                )
            decision = StrategyDecision(
                strategy=AnalysisStrategy.CODE,
                confidence=0.75,
                reasoning=f"LLM策略判定失败，使用项目内确定性趋势分析兜底: {exc}",
                suggested_code_approach="读取月周天源表的目标粒度良率行并计算趋势",
            )
            workflow_steps.append(
                AnalysisWorkflowStep(
                    name="分析策略判定",
                    status="warning",
                    detail=decision.reasoning,
                )
            )
        else:
            workflow_steps.append(
                AnalysisWorkflowStep(
                    name="分析策略判定",
                    status="success",
                    detail=f"strategy={decision.strategy}; confidence={decision.confidence:.2f}; {decision.reasoning}",
                )
            )

        if self._can_run_ct_trend(user_query, parsed_request):
            result = self._execute_ct_trend_analysis(
                request=parsed_request,
                resolved_file=resolved_file,
                schema=schema,
                decision=decision,
            )
            workflow_steps.append(
                AnalysisWorkflowStep(
                    name="数据分析",
                    status="success" if result.success else "failed",
                    detail="使用内置 CT 良率趋势分析器。" if result.success else result.error_message,
                )
            )
        elif self._can_run_daily_yield_trend(user_query, parsed_request):
            result = self._execute_daily_yield_trend_analysis(
                request=parsed_request,
                resolved_file=resolved_file,
                schema=schema,
                decision=decision,
            )
            workflow_steps.append(
                AnalysisWorkflowStep(
                    name="数据分析",
                    status="success" if result.success else "failed",
                    detail=(
                        f"使用内置{_grain_label(parsed_request.time_grain)}良率趋势分析器。"
                        if result.success
                        else result.error_message
                    ),
                )
            )
        elif decision.strategy == AnalysisStrategy.CODE:
            result = self._execute_code_analysis(user_query, resolved_file.path, schema, decision)
            workflow_steps.append(
                AnalysisWorkflowStep(
                    name="数据分析",
                    status="success" if result.success else "failed",
                    detail="生成 pandas 代码并执行。" if result.success else result.error_message,
                )
            )
        else:
            result = self._execute_llm_direct_analysis(user_query, schema, decision)
            workflow_steps.append(
                AnalysisWorkflowStep(
                    name="数据分析",
                    status="success" if result.success else "failed",
                    detail="使用 LLM 直接分析。" if result.success else result.error_message,
                )
            )

        result.parsed_request = parsed_request
        result.source_file_path = resolved_file.path
        result.memory_candidates = memory_candidates
        result.workflow_steps = workflow_steps

        if result.success:
            self._record_pending_memory(
                result=result,
                request=parsed_request,
                user_query=user_query,
                resolved_file=resolved_file,
                decision=decision,
            )

        return result

    def confirm_memory(
        self,
        record_id: str,
        corrections: dict[str, Any] | None = None,
    ) -> AnalysisMemoryRecord:
        """Mark a pending memory record as confirmed, optionally applying corrections."""
        return self._memory_store.confirm(record_id, corrections=corrections)

    def reject_memory(self, record_id: str) -> AnalysisMemoryRecord:
        """Mark a pending memory record as rejected."""
        return self._memory_store.reject(record_id)

    def correct_memory(self, record_id: str, correction: str) -> AnalysisMemoryRecord:
        """Mark a pending memory record as corrected with a user explanation."""
        return self._memory_store.correct(record_id, correction)

    def _execute_code_analysis(
        self,
        user_query: str,
        file_path: Path,
        schema: str,
        decision: StrategyDecision,
    ) -> AnalysisResult:
        try:
            code = self._code_generator.generate_code(
                schema=schema,
                user_demand=user_query,
                file_path=str(file_path),
            )
        except Exception as exc:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.CODE,
                strategy_decision=decision,
                schema=schema,
                error_message=f"代码生成失败: {exc}",
            )

        try:
            exec_result = self._code_executor.execute(code, timeout=60)
        except Exception as exc:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.CODE,
                strategy_decision=decision,
                schema=schema,
                error_message=f"代码执行失败: {exc}",
            )

        if not exec_result.success:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.CODE,
                strategy_decision=decision,
                schema=schema,
                result_text=exec_result.stdout,
                error_message=exec_result.error_message,
            )

        return AnalysisResult(
            success=True,
            strategy_used=AnalysisStrategy.CODE,
            strategy_decision=decision,
            result_text=exec_result.stdout,
            schema=schema,
        )

    def _execute_llm_direct_analysis(
        self,
        user_query: str,
        schema: str,
        decision: StrategyDecision,
    ) -> AnalysisResult:
        from yield_report.shared_kernel.infrastructure.llm_handler import llm_manager

        user_message = (
            f"## 用户需求\n{user_query}\n\n"
            f"## 数据表结构\n{schema}\n\n"
            "请根据以上数据表结构完成用户的数据分析需求。"
        )

        try:
            result_text = llm_manager.chat(
                provider=self._llm_provider,
                messages=[{"role": "user", "content": user_message}],
                system_prompt=LLM_DIRECT_ANALYSIS_PROMPT,
                temperature=0.3,
                max_tokens=4096,
            )
        except Exception as exc:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.LLM_DIRECT,
                strategy_decision=decision,
                schema=schema,
                error_message=f"LLM 直接分析失败: {exc}",
            )

        return AnalysisResult(
            success=True,
            strategy_used=AnalysisStrategy.LLM_DIRECT,
            strategy_decision=decision,
            result_text=result_text,
            schema=schema,
        )

    def _execute_ct_trend_analysis(
        self,
        *,
        request: AnalysisQueryRequest,
        resolved_file: ResolvedAnalysisFile,
        schema: str,
        decision: StrategyDecision,
    ) -> AnalysisResult:
        product_model = (request.product_models or [""])[0]
        if not product_model:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.CODE,
                strategy_decision=decision,
                schema=schema,
                error_message="未识别到产品型号，无法执行 CT 良率趋势分析。",
            )

        try:
            trend = self._ct_trend_analyzer.analyze(
                file_path=resolved_file.path,
                product_model=product_model,
                days=7,
            )
        except CtYieldTrendAnalysisError as exc:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.CODE,
                strategy_decision=decision,
                schema=schema,
                error_message=f"CT 良率趋势分析失败: {exc}",
            )

        return AnalysisResult(
            success=True,
            strategy_used=AnalysisStrategy.CODE,
            strategy_decision=decision,
            result_text=trend.result_text,
            schema=schema,
        )

    def _execute_daily_yield_trend_analysis(
        self,
        *,
        request: AnalysisQueryRequest,
        resolved_file: ResolvedAnalysisFile,
        schema: str,
        decision: StrategyDecision,
    ) -> AnalysisResult:
        product_model = (request.product_models or [""])[0]
        if not product_model:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.CODE,
                strategy_decision=decision,
                schema=schema,
                error_message="未识别到产品型号，无法执行良率趋势分析。",
            )

        try:
            trend = self._daily_yield_trend_analyzer.analyze(
                file_path=resolved_file.path,
                product_model=product_model,
                time_grain=request.time_grain or "daily",
                requested_periods=request.requested_periods,
            )
        except DailyYieldTrendAnalysisError as exc:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.CODE,
                strategy_decision=decision,
                schema=schema,
                error_message=f"良率趋势分析失败: {exc}",
            )

        requested_grain = request.time_grain or "daily"
        actual_grain = getattr(trend, "time_grain", requested_grain)
        if actual_grain != requested_grain:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.CODE,
                strategy_decision=decision,
                schema=schema,
                error_message=(
                    f"分析结果粒度不匹配: requested={requested_grain}, actual={actual_grain}"
                ),
                goal_alignment={
                    "requested_time_grain": requested_grain,
                    "actual_time_grain": actual_grain,
                    "requested_periods": request.requested_periods,
                    "actual_period_count": getattr(trend, "actual_period_count", None),
                },
            )

        return AnalysisResult(
            success=True,
            strategy_used=AnalysisStrategy.CODE,
            strategy_decision=decision,
            result_text=trend.result_text,
            schema=schema,
            warnings=list(getattr(trend, "warnings", [])),
            goal_alignment={
                "requested_time_grain": requested_grain,
                "actual_time_grain": actual_grain,
                "requested_periods": request.requested_periods,
                "actual_period_count": getattr(trend, "actual_period_count", None),
            },
        )

    def _record_pending_memory(
        self,
        *,
        result: AnalysisResult,
        request: AnalysisQueryRequest,
        user_query: str,
        resolved_file: ResolvedAnalysisFile,
        decision: StrategyDecision,
    ) -> None:
        try:
            record = self._memory_store.record_pending(
                request=request,
                user_query=user_query,
                resolved_file=resolved_file.path,
                report_file_name=resolved_file.report_file_name,
                processing_method=decision.strategy.value,
                notes=f"source={resolved_file.source}; matched_memory={resolved_file.matched_memory_id or ''}",
            )
        except Exception as exc:
            logger.warning("Failed to write pending analysis memory: %s", exc)
            return

        result.memory_record_id = record.id

    def _can_run_ct_trend(
        self,
        user_query: str,
        request: AnalysisQueryRequest,
    ) -> bool:
        return self._ct_trend_analyzer.can_handle(
            user_query=user_query,
            target_metrics=request.target_metrics,
            analysis_logic=request.analysis_logic,
        )

    def _can_run_daily_yield_trend(
        self,
        user_query: str,
        request: AnalysisQueryRequest,
    ) -> bool:
        return self._daily_yield_trend_analyzer.can_handle(
            user_query=user_query,
            target_metrics=request.target_metrics,
            analysis_logic=request.analysis_logic,
            time_grain=request.time_grain,
        )


def _describe_request(request: AnalysisQueryRequest) -> str:
    source = request.source_file_type.value if request.source_file_type else "未指定"
    models = ", ".join(request.product_models) if request.product_models else "未指定"
    metrics = ", ".join(request.target_metrics) if request.target_metrics else "未指定"
    dates = f"{request.start_date or '未指定'} ~ {request.end_date or '未指定'}"
    logic = request.analysis_logic or "未指定"
    grain = request.time_grain or "未指定"
    periods = request.requested_periods if request.requested_periods is not None else "未指定"
    return (
        f"source={source}; models={models}; dates={dates}; metrics={metrics}; "
        f"grain={grain}; periods={periods}; logic={logic}"
    )


def _grain_label(time_grain: str) -> str:
    return {"monthly": "月度", "weekly": "周度", "daily": "日度"}.get(
        time_grain or "daily",
        "日度",
    )
