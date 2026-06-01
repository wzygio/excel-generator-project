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

logger = logging.getLogger(__name__)


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
    ) -> None:
        self._llm_provider = llm_provider or "deepseek"
        self._query_parser = query_parser or AnalysisQueryParser(provider=self._llm_provider)
        self._memory_store = memory_store or AnalysisMemoryStore()
        self._file_resolver = file_resolver or AnalysisFileResolver(resources_dir=resources_dir)
        self._selector = selector or AnalysisStrategySelector(provider=self._llm_provider)
        self._code_generator = code_generator or CodeGenerator()
        self._code_executor = code_executor or CodeExecutor()

    def analyze(
        self,
        user_query: str,
        file_path: Path | None = None,
        file_name: str | None = None,
    ) -> AnalysisResult:
        """Run the complete module-2 analysis workflow."""
        try:
            parsed_request = self._query_parser.parse(
                user_query,
                provider=self._llm_provider,
            )
        except AnalysisQueryParserError as exc:
            if file_path is None and file_name is None:
                return AnalysisResult(success=False, error_message=f"需求解析失败: {exc}")
            logger.warning("Analysis query parsing failed; continuing with explicit file: %s", exc)
            parsed_request = AnalysisQueryRequest(
                user_intent=user_query,
                uncertainty_notes=f"需求解析失败，已使用显式文件继续: {exc}",
            )

        memory_candidates = self._memory_store.find_candidates(parsed_request)

        try:
            resolved_file = self._file_resolver.resolve(
                request=parsed_request,
                user_query=user_query,
                file_path=file_path,
                file_name=file_name,
                memory_candidates=memory_candidates,
            )
        except AnalysisFileResolveError as exc:
            return AnalysisResult(
                success=False,
                parsed_request=parsed_request,
                memory_candidates=memory_candidates,
                error_message=f"数据文件定位失败: {exc}",
            )

        logger.info("Analysis source resolved: %s (%s)", resolved_file.path, resolved_file.source)

        try:
            schema = extract_schema(str(resolved_file.path))
        except Exception as exc:
            return AnalysisResult(
                success=False,
                parsed_request=parsed_request,
                source_file_path=resolved_file.path,
                memory_candidates=memory_candidates,
                error_message=f"提取数据表 Schema 失败: {exc}",
            )

        try:
            decision = self._selector.decide(
                user_query=user_query,
                schema=schema,
                provider=self._llm_provider,
            )
        except Exception as exc:
            return AnalysisResult(
                success=False,
                parsed_request=parsed_request,
                source_file_path=resolved_file.path,
                memory_candidates=memory_candidates,
                schema=schema,
                error_message=f"分析策略判定失败: {exc}",
            )

        if decision.strategy == AnalysisStrategy.CODE:
            result = self._execute_code_analysis(user_query, resolved_file.path, schema, decision)
        else:
            result = self._execute_llm_direct_analysis(user_query, schema, decision)

        result.parsed_request = parsed_request
        result.source_file_path = resolved_file.path
        result.memory_candidates = memory_candidates

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
        from shared_kernel.infrastructure.llm_handler import llm_manager

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
