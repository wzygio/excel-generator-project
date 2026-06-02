"""Deterministic daily-yield trend analyzer for monthly/weekly/daily reports."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

XLSX_MAGIC = b"PK\x03\x04"


class DailyYieldTrendAnalysisError(Exception):
    """Raised when daily yield trend analysis cannot be completed."""


@dataclass
class DailyYieldPoint:
    label: str
    yield_value: float | None

    @property
    def is_valid(self) -> bool:
        return self.yield_value is not None and self.yield_value > 0


@dataclass
class DailyYieldTrendResult:
    product_model: str
    file_path: Path
    sheet_name: str
    metric_name: str
    points: list[DailyYieldPoint]
    result_text: str


class DailyYieldTrendAnalyzer:
    """Read the generic daily-yield row and produce a concise trend conclusion."""

    preferred_sheets = ("屏体综合良率", "MVI", "CT")
    preferred_metrics = ("屏体综合良率", "MVI良率", "CT良率")

    def can_handle(
        self,
        *,
        user_query: str,
        target_metrics: list[str],
        analysis_logic: str,
    ) -> bool:
        text = user_query.upper()
        metric_text = " ".join(target_metrics).upper()
        has_ct = "CT" in text or "CT" in metric_text
        has_yield = "良率" in user_query or "良率" in " ".join(target_metrics)
        has_trend = any(keyword in user_query for keyword in ["趋势", "变化", "波动"]) or (
            "趋势" in analysis_logic or "TREND" in analysis_logic.upper()
        )
        return has_yield and has_trend and not has_ct

    def analyze(
        self,
        file_path: Path,
        product_model: str,
        days: int = 7,
    ) -> DailyYieldTrendResult:
        rows_by_sheet = self._read_candidate_sheets(file_path)
        for sheet_name in self.preferred_sheets:
            rows = rows_by_sheet.get(sheet_name)
            if not rows:
                continue
            try:
                return self._analyze_rows(
                    file_path=file_path,
                    sheet_name=sheet_name,
                    rows=rows,
                    product_model=product_model,
                    days=days,
                )
            except DailyYieldTrendAnalysisError:
                logger.debug("Daily yield sheet not usable: %s", sheet_name, exc_info=True)
                continue

        raise DailyYieldTrendAnalysisError(
            f"Cannot find daily yield trend row for product={product_model}"
        )

    def _analyze_rows(
        self,
        *,
        file_path: Path,
        sheet_name: str,
        rows: list[list[Any]],
        product_model: str,
        days: int,
    ) -> DailyYieldTrendResult:
        header_index = self._find_header_row(rows)
        header = rows[header_index]
        product_col = self._find_header_col(header, ["ProductCode", "产品型号"])
        date_cols = self._find_daily_columns(header)
        if product_col is None:
            raise DailyYieldTrendAnalysisError("Cannot identify product column")
        if not date_cols:
            raise DailyYieldTrendAnalysisError("Cannot identify daily columns")

        row, metric_name = self._find_yield_row(
            rows=rows,
            start_index=header_index + 1,
            product_col=product_col,
            product_model=product_model,
        )
        chosen_cols = date_cols[-days:]
        points = [
            DailyYieldPoint(
                label=str(header[col_index]).strip(),
                yield_value=_to_float(_cell(row, col_index)),
            )
            for col_index in chosen_cols
        ]
        result_text = self._format_result(
            file_path=file_path,
            product_model=product_model,
            sheet_name=sheet_name,
            metric_name=metric_name,
            points=points,
        )
        return DailyYieldTrendResult(
            product_model=product_model,
            file_path=file_path,
            sheet_name=sheet_name,
            metric_name=metric_name,
            points=points,
            result_text=result_text,
        )

    def _read_candidate_sheets(self, file_path: Path) -> dict[str, list[list[Any]]]:
        if not _is_standard_xlsx(file_path):
            raise DailyYieldTrendAnalysisError("Daily yield analyzer requires standard xlsx")

        from openpyxl import load_workbook

        workbook = load_workbook(file_path, data_only=True, read_only=True)
        try:
            rows_by_sheet: dict[str, list[list[Any]]] = {}
            for sheet_name in workbook.sheetnames:
                worksheet = workbook[sheet_name]
                reset_dimensions = getattr(worksheet, "reset_dimensions", None)
                if callable(reset_dimensions):
                    try:
                        reset_dimensions()
                    except Exception:
                        logger.debug("Unable to reset worksheet dimensions", exc_info=True)
                rows_by_sheet[sheet_name] = [list(row) for row in worksheet.iter_rows(values_only=True)]
            return rows_by_sheet
        finally:
            workbook.close()

    @staticmethod
    def _find_header_row(rows: list[list[Any]]) -> int:
        for index, row in enumerate(rows[:12]):
            joined = " ".join(str(cell) for cell in row if cell is not None)
            if "ProductCode" in joined or "产品型号" in joined:
                return index
        raise DailyYieldTrendAnalysisError("Cannot identify header row")

    @staticmethod
    def _find_header_col(row: list[Any], keywords: list[str]) -> int | None:
        for index, cell in enumerate(row):
            text = str(cell or "")
            if any(keyword in text for keyword in keywords):
                return index
        return None

    @staticmethod
    def _find_daily_columns(row: list[Any]) -> list[int]:
        columns: list[int] = []
        for index, cell in enumerate(row):
            text = str(cell or "").strip()
            if re.match(r"^\d{1,2}/\d{1,2}$", text):
                columns.append(index)
        return columns

    def _find_yield_row(
        self,
        *,
        rows: list[list[Any]],
        start_index: int,
        product_col: int,
        product_model: str,
    ) -> tuple[list[Any], str]:
        current_product = ""
        expected_product = product_model.upper()
        for row in rows[start_index:]:
            product_value = str(_cell(row, product_col) or "").strip()
            if product_value:
                current_product = product_value.upper()
            if current_product != expected_product:
                continue
            for metric_name in self.preferred_metrics:
                if any(str(cell or "").strip() == metric_name for cell in row[:8]):
                    return row, metric_name
        raise DailyYieldTrendAnalysisError(f"Cannot find yield row for product={product_model}")

    @staticmethod
    def _format_result(
        *,
        file_path: Path,
        product_model: str,
        sheet_name: str,
        metric_name: str,
        points: list[DailyYieldPoint],
    ) -> str:
        valid_points = [point for point in points if point.is_valid]
        lines = [
            f"## {product_model} 最近一周日度良率变化趋势",
            "",
            f"- 数据源: `{file_path}`",
            f"- Sheet: `{sheet_name}`",
            f"- 指标行: `{metric_name}`",
            "",
            "| 日期 | 日度良率 | 数据状态 |",
            "| --- | ---: | --- |",
        ]
        for point in points:
            yield_text = "-" if point.yield_value is None else _format_percent(point.yield_value)
            status = "有效" if point.is_valid else "无有效良率"
            lines.append(f"| {point.label} | {yield_text} | {status} |")

        lines.extend(["", "### 核心结论"])
        if len(valid_points) >= 2:
            first = valid_points[0]
            last = valid_points[-1]
            delta = (last.yield_value or 0) - (first.yield_value or 0)
            average = sum(point.yield_value or 0 for point in valid_points) / len(valid_points)
            min_point = min(valid_points, key=lambda point: point.yield_value or 0)
            max_point = max(valid_points, key=lambda point: point.yield_value or 0)
            direction = "上升" if delta > 0 else "下降" if delta < 0 else "持平"
            lines.append(f"- 有效日期 {len(valid_points)}/{len(points)} 天。")
            lines.append(
                f"- 良率从 {first.label} 的 {_format_percent(first.yield_value)} "
                f"到 {last.label} 的 {_format_percent(last.yield_value)}，"
                f"{direction} {_format_pct_points(delta)}。"
            )
            lines.append(
                f"- 最近一周平均良率 {_format_percent(average)}；最低为 {min_point.label} "
                f"{_format_percent(min_point.yield_value)}，最高为 {max_point.label} "
                f"{_format_percent(max_point.yield_value)}。"
            )
        elif len(valid_points) == 1:
            only = valid_points[0]
            lines.append(
                f"- 最近一周只有 1 天存在有效良率：{only.label} "
                f"{_format_percent(only.yield_value)}，不足以判断连续趋势。"
            )
        else:
            lines.append("- 最近一周没有有效良率数据，无法判断趋势。")
        return "\n".join(lines)


def _is_standard_xlsx(path: Path) -> bool:
    try:
        with Path(path).open("rb") as file:
            return file.read(4) == XLSX_MAGIC
    except OSError:
        return False


def _cell(row: list[Any] | None, index: int | None) -> Any:
    if row is None or index is None or index >= len(row):
        return None
    return row[index]


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.2f}%"


def _format_pct_points(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value * 100:.2f} pct"
