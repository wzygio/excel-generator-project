from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from yield_report.core.analysis_query_parser import AnalysisQueryRequest
from yield_report.core.query_parser import ReportType
from yield_report.infrastructure.analysis_file_resolver import (
    AnalysisFileResolveError,
    AnalysisFileResolver,
)
from yield_report.infrastructure.analysis_memory import AnalysisMemoryCandidate

DECRYPTED_OUTPUT = Path("output") / "artifacts" / "workbooks" / "decrypted"
NORMALIZED_OUTPUT = Path("output") / "artifacts" / "workbooks" / "normalized"


def _request() -> AnalysisQueryRequest:
    return AnalysisQueryRequest(
        source_file_type=ReportType.DAILY_YIELD,
        file_keywords=["月周天", "良率"],
        product_models=["M678"],
        target_metrics=["CT良率"],
        analysis_logic="趋势分析",
        user_intent="分析趋势",
    )


def test_resolver_prefers_decrypted_file(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    decrypted = tmp_path / DECRYPTED_OUTPUT
    resources.mkdir()
    decrypted.mkdir(parents=True)
    plain = resources / "V3良率及不良率By月周天汇总报表.xlsx"
    normalized = decrypted / plain.name
    plain.write_bytes(b"raw")
    normalized.write_bytes(b"PK\x03\x04")

    resolver = AnalysisFileResolver(resources_dir=resources)
    result = resolver.resolve(request=_request(), user_query="query")

    assert result.path == normalized
    assert result.source == "local_fuzzy"
    assert result.was_decrypted is False


def test_resolver_prefers_standard_xlsx_when_multiple_decrypted_candidates(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    decrypted = tmp_path / DECRYPTED_OUTPUT
    decrypted.mkdir(parents=True)
    encrypted = decrypted / "V3良率及不良率By月周天汇总报表.xlsx"
    standard = decrypted / "V3良率及不良率By月周天汇总报表_decrypted.xlsx"
    encrypted.write_bytes(b"\x00\x00\x00\x00encrypted")
    standard.write_bytes(b"PK\x03\x04standard")

    resolver = AnalysisFileResolver(resources_dir=resources)
    result = resolver.resolve(request=_request(), user_query="query")

    assert result.path == standard


def test_resolver_normalizes_nonstandard_file_inside_decrypted_dir(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    decrypted = tmp_path / DECRYPTED_OUTPUT
    normalized = tmp_path / NORMALIZED_OUTPUT
    decrypted.mkdir(parents=True)
    encrypted = decrypted / "V3良率及不良率By月周天汇总报表.xlsx"
    encrypted.write_bytes(b"\x00\x00\x00\x00encrypted")
    calls: list[tuple[Path, Path]] = []

    def fake_decrypt(path: Path, output_dir: Path) -> Path:
        calls.append((path, output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / path.name
        output.write_bytes(b"PK\x03\x04standard")
        return output

    resolver = AnalysisFileResolver(resources_dir=resources, decrypt_func=fake_decrypt)
    result = resolver.resolve(request=_request(), user_query="query")

    assert calls == [(encrypted, normalized)]
    assert result.path == normalized / encrypted.name
    assert result.was_decrypted is True


def test_resolver_decrypts_resource_file_when_needed(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    resources.mkdir()
    source = resources / "V3良率及不良率By月周天汇总报表.xlsx"
    source.write_bytes(b"raw")

    calls: list[Path] = []

    def fake_decrypt(path: Path, output_dir: Path) -> Path:
        calls.append(path)
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / path.name
        output.write_bytes(b"PK\x03\x04")
        return output

    resolver = AnalysisFileResolver(resources_dir=resources, decrypt_func=fake_decrypt)
    result = resolver.resolve(request=_request(), user_query="query")

    assert calls == [source]
    assert result.path == tmp_path / DECRYPTED_OUTPUT / source.name
    assert result.was_decrypted is True


def test_resolver_uses_memory_candidate_before_fuzzy_search(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    resources.mkdir()
    memory_file = resources / "memory-match.xlsx"
    fuzzy_file = resources / "V3良率及不良率By月周天汇总报表.xlsx"
    memory_file.write_bytes(b"PK\x03\x04")
    fuzzy_file.write_bytes(b"PK\x03\x04")

    candidate = AnalysisMemoryCandidate(
        record_id="abc",
        score=10,
        local_file_name=memory_file.name,
        local_file_path=str(memory_file),
        report_file_name="remembered",
        source_file_type=ReportType.DAILY_YIELD,
    )

    resolver = AnalysisFileResolver(resources_dir=resources)
    result = resolver.resolve(
        request=_request(),
        user_query="query",
        memory_candidates=[candidate],
    )

    assert result.source == "memory"
    assert result.matched_memory_id == "abc"
    assert result.path.name == memory_file.name


def test_resolver_ignores_memory_file_for_different_declared_product(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    resources.mkdir()
    memory_file = resources / "V3良率及不良率By月周天汇总报表_结束日期2026-06-14_产品型号C522.xlsx"
    fuzzy_file = resources / "V3良率及不良率By月周天汇总报表_结束日期2026-06-03_产品型号M678.xlsx"
    memory_file.write_bytes(b"PK\x03\x04")
    fuzzy_file.write_bytes(b"PK\x03\x04")

    candidate = AnalysisMemoryCandidate(
        record_id="abc",
        score=10,
        local_file_name=memory_file.name,
        local_file_path=str(memory_file),
        report_file_name="remembered",
        source_file_type=ReportType.DAILY_YIELD,
        product_models=["C522"],
    )

    resolver = AnalysisFileResolver(resources_dir=resources)
    result = resolver.resolve(
        request=_request(),
        user_query="query",
        memory_candidates=[candidate],
    )

    assert result.source == "local_fuzzy"
    assert result.path.name == fuzzy_file.name


def test_resolver_calls_acquisition_when_no_local_file(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    resources.mkdir()
    downloaded = tmp_path / "downloaded.xlsx"
    downloaded.write_bytes(b"raw")
    calls: list[str] = []

    class FakeAcquisition:
        def process_user_query(self, query: str):
            calls.append(query)
            return SimpleNamespace(
                results=[
                    SimpleNamespace(
                        success=True,
                        file_path=downloaded,
                        file_description="Downloaded Daily",
                    )
                ]
            )

    def fake_decrypt(path: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / path.name
        output.write_bytes(b"PK\x03\x04")
        return output

    resolver = AnalysisFileResolver(
        resources_dir=resources,
        decrypt_func=fake_decrypt,
        acquisition_orchestrator=FakeAcquisition(),
    )
    result = resolver.resolve(request=_request(), user_query="query")

    assert calls
    assert result.source == "download"
    assert result.path == tmp_path / DECRYPTED_OUTPUT / downloaded.name


def test_resolver_ignores_local_file_for_different_declared_product(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    resources.mkdir()
    wrong = resources / "V3良率及不良率By月周天汇总报表_结束日期2026-06-01_产品型号M678.xlsx"
    wrong.write_bytes(b"PK\x03\x04")
    downloaded = tmp_path / "downloaded-c522.xlsx"
    downloaded.write_bytes(b"PK\x03\x04")
    calls: list[str] = []

    class FakeAcquisition:
        def process_user_query(self, query: str):
            calls.append(query)
            return SimpleNamespace(
                results=[
                    SimpleNamespace(
                        success=True,
                        file_path=downloaded,
                        file_description="Downloaded C522 Daily",
                    )
                ]
            )

    def fake_decrypt(path: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / path.name
        output.write_bytes(b"PK\x03\x04")
        return output

    resolver = AnalysisFileResolver(
        resources_dir=resources,
        decrypt_func=fake_decrypt,
        acquisition_orchestrator=FakeAcquisition(),
    )

    request = _request()
    request.product_models = ["C522"]
    result = resolver.resolve(request=request, user_query="query")

    assert calls
    assert result.source == "download"
    assert result.path == tmp_path / DECRYPTED_OUTPUT / downloaded.name


def test_resolver_does_not_use_ct_exception_for_daily_yield_request(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    resources.mkdir()
    ct_exception = resources / "CT良率异常波动管理表.xlsx"
    ct_exception.write_bytes(b"PK\x03\x04")

    class EmptyAcquisition:
        def process_user_query(self, query: str):
            return SimpleNamespace(results=[])

    resolver = AnalysisFileResolver(
        resources_dir=resources,
        acquisition_orchestrator=EmptyAcquisition(),
    )

    with pytest.raises(AnalysisFileResolveError):
        resolver.resolve(request=_request(), user_query="query")


def test_resolver_does_not_treat_decrypted_priority_as_match(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    decrypted = tmp_path / DECRYPTED_OUTPUT
    decrypted.mkdir(parents=True)
    unrelated = decrypted / "unrelated_target_file.xlsx"
    unrelated.write_bytes(b"PK\x03\x04")

    class EmptyAcquisition:
        def process_user_query(self, query: str):
            return SimpleNamespace(results=[])

    resolver = AnalysisFileResolver(
        resources_dir=resources,
        acquisition_orchestrator=EmptyAcquisition(),
    )

    with pytest.raises(AnalysisFileResolveError):
        resolver.resolve(request=_request(), user_query="query")
