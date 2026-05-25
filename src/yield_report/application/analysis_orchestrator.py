"""analysis_orchestrator.py - 数据分析编排器 (Application 层)

AnalysisOrchestrator 是"数据分析层"的总控模块。
它串联了完整的数据分析工作流:

工作流:
    用户输入自然语言分析需求
        → Step 1: 提取参数 (报表名、产品型号、时间范围、分析目标)
        → Step 2: 定位/下载源数据文件
        → Step 3: 提取数据表 Schema
        → Step 4: LLM 判定分析策略 (code 执行 vs LLM 直接分析)
        → Step 5: 执行分析
            - code 路径: CodeGenerator 生成 pandas 代码 → CodeExecutor 执行
            - llm_direct 路径: 将数据 + 用户需求发送 LLM 直接分析
        → Step 6: 返回结构化结果

使用方式:
    orchestrator = AnalysisOrchestrator()
    result = orchestrator.analyze(
        user_query="从《V3良率及不良率By月周天汇总报表》中分析M678近一个月日度良率趋势",
        file_path=Path("resources/V3良率及不良率By月周天汇总报表.xlsx"),
    )
    print(result.result_text)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from yield_report.core.analysis_selector import (
    AnalysisStrategy,
    AnalysisStrategySelector,
    StrategyDecision,
)
from yield_report.infrastructure.code_executor import CodeExecutor, ExecutionResult
from yield_report.infrastructure.code_generator import CodeGenerator, extract_schema
from yield_report.infrastructure.local_file_loader import (
    LocalFileLoader,
    LocalFileNotFoundError,
)

logger = logging.getLogger(__name__)


# ================================================================
# 数据模型
# ================================================================


@dataclass
class AnalysisResult:
    """数据分析结果。

    Attributes:
        success: 是否成功
        strategy_used: 实际使用的分析策略
        strategy_decision: 策略判定的完整结果
        result_text: 分析结果文本
        schema: 数据表 Schema
        error_message: 失败时的错误信息
    """

    success: bool
    strategy_used: AnalysisStrategy | None = None
    strategy_decision: StrategyDecision | None = None
    result_text: str = ""
    schema: str = ""
    error_message: str = ""

    def summary(self) -> str:
        """生成简短摘要。"""
        if self.success:
            return (
                f"✅ 分析完成\n"
                f"   策略: {self.strategy_used}\n"
                f"   判定理由: {self.strategy_decision.reasoning if self.strategy_decision else 'N/A'}\n"
                f"   结果长度: {len(self.result_text)} 字符"
            )
        else:
            return f"❌ 分析失败: {self.error_message}"


# ================================================================
# LLM 直接分析 Prompt
# ================================================================

LLM_DIRECT_ANALYSIS_PROMPT = """你是一个专业的良率数据分析师。请根据以下数据表结构和用户需求，直接进行分析并给出结论。

## 分析要求
1. 先理解数据结构，识别关键字段
2. 根据用户需求进行针对性分析
3. 用中文输出，结构清晰
4. 如果有数据支持，给出具体数值
5. 如果数据不足以回答用户问题，诚实地说明

## 输出格式
请用以下格式输出:
- **数据概览**: 对数据表的整体理解
- **分析过程**: 逐步分析过程
- **核心发现**: 最重要的分析结论
- **建议**: (如有)基于分析的后续建议
"""


# ================================================================
# AnalysisOrchestrator
# ================================================================


class AnalysisOrchestrator:
    """数据分析编排器。

    协调 StrategySelector → CodeGenerator/LLM → CodeExecutor 的完整流程。
    """

    def __init__(
        self,
        llm_provider: str | None = None,
        resources_dir: Path | None = None,
    ) -> None:
        self._selector = AnalysisStrategySelector(provider=llm_provider)
        self._code_generator = CodeGenerator()
        self._code_executor = CodeExecutor()
        self._local_loader = LocalFileLoader() if not resources_dir else None
        self._resources_dir = resources_dir or Path("resources")
        self._llm_provider = llm_provider or "deepseek"

    # ================================================================
    # 公共接口
    # ================================================================

    def analyze(
        self,
        user_query: str,
        file_path: Path | None = None,
        file_name: str | None = None,
    ) -> AnalysisResult:
        """执行完整的数据分析工作流。

        Args:
            user_query: 用户的自然语言分析需求
            file_path: 目标 Excel 文件的绝对路径（可选）
            file_name: 目标文件名，将在 resources/ 下查找（可选）

        Returns:
            AnalysisResult: 分析结果

        若 file_path 和 file_name 均未提供，将从 resources/ 查找第一个 .xlsx 文件。
        """
        # ----- Step 1: 定位数据文件 -----
        try:
            resolved_path = self._resolve_file(file_path, file_name)
        except LocalFileNotFoundError as e:
            return AnalysisResult(
                success=False,
                error_message=f"数据文件未找到: {e}",
            )

        logger.info("数据文件已定位: %s", resolved_path)

        # ----- Step 2: 提取 Schema -----
        try:
            schema = extract_schema(str(resolved_path))
        except Exception as e:
            return AnalysisResult(
                success=False,
                error_message=f"提取数据表 Schema 失败: {e}",
            )
        logger.info("Schema 提取成功 (%d 字符)", len(schema))

        # ----- Step 3: 策略判定 -----
        try:
            decision = self._selector.decide(
                user_query=user_query,
                schema=schema,
                provider=self._llm_provider,
            )
        except Exception as e:
            return AnalysisResult(
                success=False,
                schema=schema,
                error_message=f"分析策略判定失败: {e}",
            )
        logger.info(
            "策略判定: %s (置信度: %.2f)",
            decision.strategy,
            decision.confidence,
        )

        # ----- Step 4: 执行分析 -----
        if decision.strategy == AnalysisStrategy.CODE:
            return self._execute_code_analysis(
                user_query, resolved_path, schema, decision
            )
        else:
            return self._execute_llm_direct_analysis(
                user_query, schema, decision
            )

    # ================================================================
    # 分析执行路径
    # ================================================================

    def _execute_code_analysis(
        self,
        user_query: str,
        file_path: Path,
        schema: str,
        decision: StrategyDecision,
    ) -> AnalysisResult:
        """代码执行路径: CodeGenerator → CodeExecutor。"""
        try:
            code = self._code_generator.generate_code(
                schema=schema,
                user_demand=user_query,
                file_path=str(file_path),
            )
        except Exception as e:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.CODE,
                strategy_decision=decision,
                schema=schema,
                error_message=f"代码生成失败: {e}",
            )

        logger.info("代码已生成 (%d 字符)", len(code))

        try:
            exec_result = self._code_executor.execute(code, timeout=60)
        except Exception as e:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.CODE,
                strategy_decision=decision,
                schema=schema,
                error_message=f"代码执行失败: {e}",
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
        """LLM 直接分析路径。"""
        from shared_kernel.infrastructure.llm_handler import llm_manager

        user_message = (
            f"## 用户需求\n{user_query}\n\n"
            f"## 数据表结构\n{schema}\n\n"
            f"请根据以上数据表结构完成用户的分析需求。"
        )

        try:
            result_text = llm_manager.chat(
                provider=self._llm_provider,
                messages=[{"role": "user", "content": user_message}],
                system_prompt=LLM_DIRECT_ANALYSIS_PROMPT,
                temperature=0.3,
                max_tokens=4096,
            )
        except Exception as e:
            return AnalysisResult(
                success=False,
                strategy_used=AnalysisStrategy.LLM_DIRECT,
                strategy_decision=decision,
                schema=schema,
                error_message=f"LLM 直接分析失败: {e}",
            )

        return AnalysisResult(
            success=True,
            strategy_used=AnalysisStrategy.LLM_DIRECT,
            strategy_decision=decision,
            result_text=result_text,
            schema=schema,
        )

    # ================================================================
    # 辅助方法
    # ================================================================

    def _resolve_file(
        self,
        file_path: Path | None,
        file_name: str | None,
    ) -> Path:
        """解析目标数据文件的路径。

        优先级: file_path > file_name > 自动查找 resources/ 下的 .xlsx
        """
        if file_path is not None:
            resolved = Path(file_path)
            if not resolved.exists():
                raise LocalFileNotFoundError(f"指定文件不存在: {resolved}")
            return resolved

        if file_name is not None:
            resolved = self._resources_dir / file_name
            if not resolved.exists():
                raise LocalFileNotFoundError(f"文件未找到: {resolved}")
            return resolved

        # 自动查找 resources/ 下的第一个 .xlsx 文件
        xlsx_files = list(self._resources_dir.glob("*.xlsx"))
        if not xlsx_files:
            raise LocalFileNotFoundError(
                f"resources/ 目录下没有找到 .xlsx 文件"
            )
        return xlsx_files[0]
