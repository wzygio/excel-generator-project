"""Resolve source files for the data-analysis workflow."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yield_report.core.analysis_query_parser import AnalysisQueryRequest
from yield_report.core.query_parser import REPORT_TYPE_META, ReportType
from yield_report.infrastructure.analysis_memory import AnalysisMemoryCandidate
from yield_report.infrastructure.file_decryption import decrypt_excel_file

logger = logging.getLogger(__name__)
XLSX_MAGIC = b"PK\x03\x04"


class AnalysisFileResolveError(Exception):
    """Raised when no usable analysis file can be resolved."""


@dataclass
class ResolvedAnalysisFile:
    path: Path
    source: str
    report_file_name: str = ""
    matched_memory_id: str | None = None
    was_decrypted: bool = False


DecryptFunc = Callable[[Path, Path], Path]


REPORT_TYPE_ALIASES: dict[ReportType, list[str]] = {
    ReportType.DAILY_YIELD: ["V3良率", "良率及不良率", "月周天", "日度", "良率报表"],
    ReportType.BATCH_YIELD: ["批次", "batch", "批次汇总"],
    ReportType.CT_EXCEPTION: ["CT", "异常", "波动管理"],
    ReportType.TARGET_DECOMPOSITION: ["目标", "拆解", "target"],
    ReportType.GAP_TEMPLATE: ["Gap", "模板", "分析模板"],
}


class AnalysisFileResolver:
    """Locate, download, and normalize the Excel file used for analysis."""

    def __init__(
        self,
        resources_dir: Path | None = None,
        decrypted_dir: Path | None = None,
        decrypt_func: DecryptFunc = decrypt_excel_file,
        acquisition_orchestrator: Any | None = None,
    ) -> None:
        self._resources_dir = resources_dir or Path("resources")
        self._decrypted_dir = decrypted_dir or self._resources_dir / "decrypted_files"
        self._decrypt_func = decrypt_func
        self._acquisition_orchestrator = acquisition_orchestrator

    @property
    def resources_dir(self) -> Path:
        return self._resources_dir

    @property
    def decrypted_dir(self) -> Path:
        return self._decrypted_dir

    def resolve(
        self,
        *,
        request: AnalysisQueryRequest,
        user_query: str,
        file_path: Path | None = None,
        file_name: str | None = None,
        memory_candidates: list[AnalysisMemoryCandidate] | None = None,
    ) -> ResolvedAnalysisFile:
        if file_path is not None:
            explicit_path = Path(file_path)
            if not explicit_path.exists():
                raise AnalysisFileResolveError(f"Specified file does not exist: {explicit_path}")
            path, was_decrypted = self._ensure_decrypted(explicit_path)
            return ResolvedAnalysisFile(
                path=path,
                source="explicit_path",
                report_file_name=self._report_name_for(request, path),
                was_decrypted=was_decrypted,
            )

        if file_name:
            matched = self._find_by_file_name(file_name)
            if matched is not None:
                path, was_decrypted = self._ensure_decrypted(matched)
                return ResolvedAnalysisFile(
                    path=path,
                    source="explicit_name",
                    report_file_name=self._report_name_for(request, path),
                    was_decrypted=was_decrypted,
                )

        for candidate in memory_candidates or []:
            matched = self._find_memory_file(candidate)
            if matched is not None:
                path, was_decrypted = self._ensure_decrypted(matched)
                return ResolvedAnalysisFile(
                    path=path,
                    source="memory",
                    report_file_name=candidate.report_file_name or self._report_name_for(request, path),
                    matched_memory_id=candidate.record_id,
                    was_decrypted=was_decrypted,
                )

        local_match = self._find_fuzzy_local_file(request)
        if local_match is not None:
            path, was_decrypted = self._ensure_decrypted(local_match)
            return ResolvedAnalysisFile(
                path=path,
                source="local_fuzzy",
                report_file_name=self._report_name_for(request, path),
                was_decrypted=was_decrypted,
            )

        downloaded = self._download_missing_source(request, user_query)
        if downloaded is not None:
            path, was_decrypted = self._ensure_decrypted(downloaded.path)
            downloaded.path = path
            downloaded.was_decrypted = downloaded.was_decrypted or was_decrypted
            return downloaded

        raise AnalysisFileResolveError("No matching local file found and download did not produce a file")

    def _find_by_file_name(self, file_name: str) -> Path | None:
        exact_candidates = [
            self._decrypted_dir / file_name,
            self._resources_dir / file_name,
        ]
        for candidate in exact_candidates:
            if candidate.exists() and candidate.is_file():
                return candidate

        needle = _norm(file_name)
        for candidate in self._iter_excel_files():
            if needle in _norm(candidate.name):
                return candidate
        return None

    def _find_memory_file(self, candidate: AnalysisMemoryCandidate) -> Path | None:
        if candidate.local_file_path:
            path = Path(candidate.local_file_path)
            if path.exists() and path.is_file():
                return path
        if candidate.local_file_name:
            return self._find_by_file_name(candidate.local_file_name)
        return None

    def _find_fuzzy_local_file(self, request: AnalysisQueryRequest) -> Path | None:
        scored: list[tuple[float, Path]] = []
        for path in self._iter_excel_files():
            score = self._score_file(request, path)
            if score > 0:
                scored.append((score, path))

        if scored:
            scored.sort(
                key=lambda item: (
                    item[0],
                    self._standard_priority(item[1]),
                    self._path_priority(item[1]),
                ),
                reverse=True,
            )
            return scored[0][1]

        candidates = list(self._iter_excel_files())
        if not request.source_file_type and not request.file_keywords and not request.target_metrics:
            return candidates[0] if candidates else None
        return None

    def _score_file(self, request: AnalysisQueryRequest, path: Path) -> float:
        filename = _norm(path.name)
        score = 0.0

        if request.source_file_type:
            meta_name = REPORT_TYPE_META[request.source_file_type]["name"]
            if _norm(meta_name) in filename:
                score += 20.0
            for alias in REPORT_TYPE_ALIASES.get(request.source_file_type, []):
                if _norm(alias) in filename:
                    score += 5.0

        for keyword in request.file_keywords:
            if _norm(keyword) and _norm(keyword) in filename:
                score += 4.0

        for metric in request.target_metrics:
            metric_norm = _norm(metric)
            if metric_norm and metric_norm in filename:
                score += 2.0

        return score

    def _iter_excel_files(self) -> list[Path]:
        files: list[Path] = []
        seen: set[str] = set()
        for directory in [self._decrypted_dir, self._resources_dir]:
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.xlsx")):
                key = str(path.resolve()).lower()
                if path.is_file() and key not in seen:
                    seen.add(key)
                    files.append(path)
        return files

    def _ensure_decrypted(self, path: Path) -> tuple[Path, bool]:
        path = Path(path)
        if path.suffix.lower() != ".xlsx":
            return path, False

        if self._is_inside_decrypted_dir(path):
            return path, False

        existing = self._decrypted_dir / path.name
        if existing.exists() and existing.is_file():
            return existing, False

        try:
            output_path = self._decrypt_func(path, self._decrypted_dir)
        except Exception as exc:
            raise AnalysisFileResolveError(f"Failed to decrypt or normalize file {path}: {exc}") from exc
        return output_path, True

    def _download_missing_source(
        self,
        request: AnalysisQueryRequest,
        user_query: str,
    ) -> ResolvedAnalysisFile | None:
        orchestrator = self._acquisition_orchestrator
        if orchestrator is None:
            try:
                from yield_report.application.orchestrator import DataAcquisitionOrchestrator

                orchestrator = DataAcquisitionOrchestrator()
            except Exception as exc:
                logger.warning("Could not create data acquisition orchestrator: %s", exc)
                return None

        acquisition_query = self._build_acquisition_query(request, user_query)
        try:
            result = orchestrator.process_user_query(acquisition_query)
        except Exception as exc:
            logger.warning("Data acquisition failed: %s", exc)
            return None

        for item in getattr(result, "results", []):
            if getattr(item, "success", False) and getattr(item, "file_path", None):
                path = Path(item.file_path)
                if path.exists():
                    return ResolvedAnalysisFile(
                        path=path,
                        source="download",
                        report_file_name=getattr(item, "file_description", "") or self._report_name_for(request, path),
                    )
        return None

    def _build_acquisition_query(
        self,
        request: AnalysisQueryRequest,
        user_query: str,
    ) -> str:
        parts = ["请获取用于数据分析的源表。", f"原始分析需求：{user_query}"]
        if request.source_file_type:
            meta = REPORT_TYPE_META[request.source_file_type]
            parts.append(f"报表类型：{request.source_file_type.value}（{meta['name']}）")
        if request.product_models is not None:
            parts.append(f"产品型号：{', '.join(request.product_models) if request.product_models else '全部型号'}")
        if request.start_date:
            parts.append(f"开始日期：{request.start_date}")
        if request.end_date:
            parts.append(f"结束日期：{request.end_date}")
        return "\n".join(parts)

    def _report_name_for(self, request: AnalysisQueryRequest, path: Path) -> str:
        if request.source_file_type:
            return REPORT_TYPE_META[request.source_file_type]["name"]
        return path.stem

    def _is_inside_decrypted_dir(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self._decrypted_dir.resolve())
            return True
        except ValueError:
            return False

    def _path_priority(self, path: Path) -> float:
        return 1.0 if self._is_inside_decrypted_dir(path) else 0.0

    @staticmethod
    def _standard_priority(path: Path) -> float:
        return 1.0 if _is_standard_xlsx(path) else 0.0


def _norm(value: str) -> str:
    return value.lower().replace(" ", "")


def _is_standard_xlsx(path: Path) -> bool:
    try:
        with Path(path).open("rb") as file:
            return file.read(4) == XLSX_MAGIC
    except OSError:
        return False
