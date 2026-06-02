from __future__ import annotations

from pathlib import Path

from yield_report.application.analysis_orchestrator import AnalysisOrchestrator
from yield_report.core.analysis_query_parser import AnalysisQueryRequest
from yield_report.core.analysis_selector import AnalysisStrategy, StrategyDecision
from yield_report.core.query_parser import ReportType
from yield_report.infrastructure.analysis_file_resolver import ResolvedAnalysisFile
from yield_report.infrastructure.analysis_memory import AnalysisMemoryStore
from yield_report.infrastructure.code_executor import ExecutionResult


class FakeParser:
    def __init__(self, request: AnalysisQueryRequest) -> None:
        self.request = request

    def parse(self, user_input: str, provider: str | None = None) -> AnalysisQueryRequest:
        return self.request


class FakeResolver:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.memory_candidates_seen = None

    def resolve(self, **kwargs) -> ResolvedAnalysisFile:
        self.memory_candidates_seen = kwargs.get("memory_candidates")
        return ResolvedAnalysisFile(
            path=self.path,
            source="local_fuzzy",
            report_file_name="V3良率及不良率By月周天汇总报表",
        )


class FakeSelector:
    def decide(self, user_query: str, schema: str = "", provider: str | None = None):
        return StrategyDecision(
            strategy=AnalysisStrategy.CODE,
            confidence=0.9,
            reasoning="clear trend analysis",
            suggested_code_approach="group by day",
        )


class FakeCodeGenerator:
    def generate_code(self, schema: str, user_demand: str, file_path: str) -> str:
        return "print('analysis ok')"


class FakeCodeExecutor:
    def execute(self, code: str, timeout: int = 30) -> ExecutionResult:
        return ExecutionResult(success=True, stdout="analysis ok")


class FakeCtTrendAnalyzer:
    def can_handle(self, **kwargs) -> bool:
        return False


class FakeDailyYieldTrendAnalyzer:
    def __init__(self, can_handle: bool = False) -> None:
        self._can_handle = can_handle
        self.calls: list[dict] = []

    def can_handle(self, **kwargs) -> bool:
        return self._can_handle

    def analyze(self, **kwargs):
        self.calls.append(kwargs)
        return type("DailyTrend", (), {"result_text": "daily trend ok"})()


def _request() -> AnalysisQueryRequest:
    return AnalysisQueryRequest(
        source_file_type=ReportType.DAILY_YIELD,
        file_keywords=["月周天"],
        product_models=["M678"],
        start_date="2026-05-25",
        end_date="2026-06-01",
        target_metrics=["CT良率"],
        filter_conditions={"product_model": "M678"},
        analysis_logic="趋势分析",
        user_intent="分析 M678 近一周 CT 良率趋势",
    )


def test_analysis_orchestrator_runs_full_pipeline_and_records_memory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "daily.xlsx"
    source.write_bytes(b"PK\x03\x04")
    memory = AnalysisMemoryStore(tmp_path / "memory.json")

    monkeypatch.setattr(
        "yield_report.application.analysis_orchestrator.extract_schema",
        lambda path: "schema with 日期 产品 CT良率",
    )

    orchestrator = AnalysisOrchestrator(
        query_parser=FakeParser(_request()),
        file_resolver=FakeResolver(source),
        memory_store=memory,
        selector=FakeSelector(),
        code_generator=FakeCodeGenerator(),
        code_executor=FakeCodeExecutor(),
        ct_trend_analyzer=FakeCtTrendAnalyzer(),
        daily_yield_trend_analyzer=FakeDailyYieldTrendAnalyzer(),
    )

    result = orchestrator.analyze("请分析M678近一周的日度CT良率变化趋势")

    assert result.success is True
    assert result.result_text == "analysis ok"
    assert result.source_file_path == source
    assert result.memory_record_id is not None
    assert [step.name for step in result.workflow_steps] == [
        "需求解析",
        "Agent-Memory",
        "文件扫描/下载/解密",
        "Schema提取",
        "分析策略判定",
        "数据分析",
    ]

    records = memory.list_records()
    assert len(records) == 1
    assert records[0].status == "pending"
    assert records[0].source_file_type == ReportType.DAILY_YIELD
    assert records[0].processing_method == "code"

    confirmed = orchestrator.confirm_memory(result.memory_record_id)
    assert confirmed.status == "confirmed"
    rejected = orchestrator.reject_memory(result.memory_record_id)
    assert rejected.status == "rejected"


def test_analysis_orchestrator_generates_code_with_codex_cli(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "daily.xlsx"
    source.write_bytes(b"PK\x03\x04")
    memory = AnalysisMemoryStore(tmp_path / "memory.json")

    monkeypatch.setattr(
        "yield_report.application.analysis_orchestrator.extract_schema",
        lambda path: "schema with 日期 产品 日度良率",
    )

    codex_calls: list[dict] = []

    def codex_chat(self, **kwargs):
        codex_calls.append(kwargs)
        return "print('M626 最近一周日度良率趋势: codex ok')"

    monkeypatch.setattr(
        "shared_kernel.infrastructure.codex_cli_client.CodexCLIClient.chat",
        codex_chat,
    )

    orchestrator = AnalysisOrchestrator(
        query_parser=FakeParser(
            AnalysisQueryRequest(
                source_file_type=ReportType.DAILY_YIELD,
                file_keywords=["月周天"],
                product_models=["M626"],
                start_date="2026-05-26",
                end_date="2026-06-01",
                target_metrics=["日度良率"],
                analysis_logic="趋势分析",
                user_intent="分析M626最近一周的日度良率变化趋势",
            )
        ),
        file_resolver=FakeResolver(source),
        memory_store=memory,
        selector=FakeSelector(),
        code_executor=FakeCodeExecutor(),
        ct_trend_analyzer=FakeCtTrendAnalyzer(),
        daily_yield_trend_analyzer=FakeDailyYieldTrendAnalyzer(),
    )

    result = orchestrator.analyze("请分析M626最近一周的日度良率变化趋势")

    assert result.success is True
    assert codex_calls
    assert result.result_text == "analysis ok"
    assert result.source_file_path == source


def test_analysis_orchestrator_uses_daily_yield_trend_analyzer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "daily.xlsx"
    source.write_bytes(b"PK\x03\x04")
    memory = AnalysisMemoryStore(tmp_path / "memory.json")
    daily_analyzer = FakeDailyYieldTrendAnalyzer(can_handle=True)

    monkeypatch.setattr(
        "yield_report.application.analysis_orchestrator.extract_schema",
        lambda path: "schema with 日期 产品 日度良率",
    )

    orchestrator = AnalysisOrchestrator(
        query_parser=FakeParser(
            AnalysisQueryRequest(
                source_file_type=ReportType.DAILY_YIELD,
                file_keywords=["月周天"],
                product_models=["M626"],
                start_date="2026-05-26",
                end_date="2026-06-01",
                target_metrics=["日度良率"],
                analysis_logic="趋势分析",
                user_intent="分析M626最近一周的日度良率变化趋势",
            )
        ),
        file_resolver=FakeResolver(source),
        memory_store=memory,
        selector=FakeSelector(),
        code_generator=FakeCodeGenerator(),
        code_executor=FakeCodeExecutor(),
        ct_trend_analyzer=FakeCtTrendAnalyzer(),
        daily_yield_trend_analyzer=daily_analyzer,
    )

    result = orchestrator.analyze("请分析M626最近一周的日度良率变化趋势")

    assert result.success is True
    assert result.result_text == "daily trend ok"
    assert daily_analyzer.calls
