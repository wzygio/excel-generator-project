"""Task0-Task4 orchestrator adapter for the daily_report skill."""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from yield_report.agent.spec_model import ArtifactRef, RunContext, SkillError, SkillResult
from yield_report.skills.daily_report.models import DailyReportRequest
from yield_report.skills.daily_report.task0_task2_orchestrator import (
    CommandResult,
    _count_nonblank_values,
    _find_column,
    _read_sheet_values,
    _suffix_from_request,
    compare_workbook_values,
)

TOOL_NAME = "daily_report"
DEFAULT_DUTY_WORKSPACE = Path(r"D:\wzy\工作-值班工作\相关文件")
DEFAULT_OUTPUT_PREFIX = "V3良率日报每日异常填报表"
DEFAULT_CHILD_PYTHON = "python"
TASK0_TIMEOUT_RETURNCODE = 124
TASK1_GAP_ANALYSIS_SCRIPT = (
    Path.home() / ".agents" / "skills" / "task1-gap-analysis" / "scripts" / "task1_gap_analysis.py"
)
DATA_PACKET_SHEET = "Data Packet"
UPLOAD_SHEET_CANDIDATES = ("Sheet1", "sheet1")
DAILY_YIELD_FILENAME = "V3良率及不良率By月周天汇总报表.xlsx"
BATCH_YIELD_FILENAME = "V3良率及不良率By批次汇总报表.xlsx"
TARGET_CANDIDATE_NAMES = (
    "良率目标表.xlsx",
    "2026年良率目标拆解-1017版V05 - 无公式版.xlsx",
)
DECRYPTED_TARGET_CANDIDATE_NAMES = tuple(
    f"decrypted_files/{name}" for name in TARGET_CANDIDATE_NAMES
)


class CommandTimeoutError(RuntimeError):
    """Raised when a child script exceeds its configured timeout."""

    def __init__(self, result: CommandResult) -> None:
        super().__init__(result.stderr)
        self.result = result


class Task0Task4Orchestrator:
    """Execute the external OLED duty Task0-Task4 scripts in strict order."""

    workflow = [
        "basic-preparation",
        "task1-gap-analysis",
        "task2-extract-anomalies",
        "task3-batch-month-analysis",
        "task4-daily-report-generation",
    ]

    def __init__(self, request: DailyReportRequest, context: RunContext) -> None:
        self.request = request
        self.context = context
        self.workspace = self._resolve_workspace()
        self.output_dir = Path(request.output_dir or context.output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self._resolve_output_path()

    def run(self) -> SkillResult:
        try:
            self._assert_scripts_exist()
            command_results = self._run_workflow()
            verification = verify_daily_report_workbook(self.output_path)
            comparison = (
                compare_workbook_values(
                    self.output_path,
                    self.request.reference_workbook,
                    sheet_names=(DATA_PACKET_SHEET, verification["sheet1"]["sheet"]),
                )
                if self.request.reference_workbook
                else None
            )
            success = comparison is None or comparison["match"]
            warnings = [
                result.stderr
                for result in command_results
                if result.returncode == TASK0_TIMEOUT_RETURNCODE and result.stderr
            ]
            return SkillResult(
                skill_name=TOOL_NAME,
                success=success,
                summary=(
                    f"Task0-Task4 日报流程完成: {self.output_path}"
                    if success
                    else f"Task0-Task4 日报流程完成，但与目标文件不一致: {self.output_path}"
                ),
                artifacts=[
                    ArtifactRef(
                        kind="excel",
                        path=self.output_path,
                        description="Task0-Task4 generated daily report workbook",
                        metadata={"skill": TOOL_NAME, "workflow": self.workflow},
                    )
                ],
                data={
                    "workflow": self.workflow,
                    "workspace": str(self.workspace),
                    "output_file": str(self.output_path),
                    "steps": [result.to_payload() for result in command_results],
                    "verification": verification,
                    "comparison": comparison,
                },
                warnings=warnings,
                error=None
                if success
                else SkillError(
                    code="daily_report.reference_mismatch",
                    message="Generated workbook differs from the reference workbook.",
                    recoverable=True,
                    details={"comparison": comparison},
                ),
            )
        except Exception as exc:
            return SkillResult(
                skill_name=TOOL_NAME,
                success=False,
                summary=f"Task0-Task4 日报流程失败: {exc}",
                data={
                    "workflow": self.workflow,
                    "workspace": str(self.workspace),
                    "output_file": str(self.output_path),
                },
                error=SkillError(
                    code="daily_report.orchestrator.failed",
                    message=str(exc),
                    recoverable=True,
                ),
            )

    def _resolve_workspace(self) -> Path:
        configured = (
            self.request.orchestrator_workspace
            or self.request.source_files.get("orchestrator_workspace")
            or os.getenv("YIELD_REPORT_DUTY_WORKSPACE")
            or DEFAULT_DUTY_WORKSPACE
        )
        return Path(configured).resolve()

    def _resolve_output_path(self) -> Path:
        if self.request.output_name:
            return (self.output_dir / self.request.output_name).resolve()
        suffix = _suffix_from_request(self.request)
        return (self.output_dir / f"{DEFAULT_OUTPUT_PREFIX}-{suffix}.xlsx").resolve()

    def _assert_scripts_exist(self) -> None:
        missing = [
            str(path)
            for path in (
                self._script("task0_report_download.py"),
                self._task1_script(),
                self._script("task2_extract_anomalies.py"),
                self._script("task3_batch_month_analysis.py"),
                self._script("task4_daily_report_generation.py"),
            )
            if not path.exists()
        ]
        if missing:
            raise FileNotFoundError(f"Task0-Task4 child script missing: {', '.join(missing)}")

    def _run_workflow(self) -> list[CommandResult]:
        results: list[CommandResult] = []
        results.append(self._run_task0())
        if not self.output_path.exists():
            raise FileNotFoundError(f"Task0 did not create workbook: {self.output_path}")

        if self.request.run_inspection:
            results.append(
                self._run_command(
                    "task1-gap-analysis:inspect-before",
                    self._task1_command("--inspect"),
                )
            )
        if self._task1_script().name == "task1_gap_analysis.py":
            results.append(
                self._run_command(
                    "task1-gap-analysis:self-test",
                    self._task1_command("--self-test"),
                )
            )
        results.append(self._run_command("task1-gap-analysis", self._task1_command("--write")))

        results.append(self._run_command("task2-extract-anomalies", self._task2_command("--write")))
        if self.request.run_inspection:
            results.append(
                self._run_command(
                    "task2-extract-anomalies:inspect",
                    self._task2_command("--inspect"),
                )
            )

        results.append(
            self._run_command(
                "task3-batch-month-analysis",
                self._task3_command(),
            )
        )
        results.append(
            self._run_command(
                "task4-daily-report-generation",
                self._task4_command(),
            )
        )
        return results

    def _run_task0(self) -> CommandResult:
        try:
            return self._run_command(
                "basic-preparation",
                self._task0_command(),
                timeout=self.request.task0_timeout_seconds,
            )
        except CommandTimeoutError as exc:
            if self.output_path.exists():
                _cleanup_hidden_excel_processes()
                _wait_for_file_unlock(self.output_path, timeout_seconds=20)
                return exc.result
            raise RuntimeError(exc.result.stderr) from exc

    def _task0_command(self) -> list[str]:
        command = [
            self._child_python(),
            str(self._script("task0_report_download.py")),
            "--write",
            "--output",
            str(self.output_path),
        ]
        if self.request.report_date:
            command.extend(["--end-date", self.request.report_date])
        if self.request.download_sources:
            command.append("--download-sources")
        return command

    def _task1_script(self) -> Path:
        configured = self.request.source_files.get("task1_overstock_impact_script") or os.getenv(
            "YIELD_REPORT_TASK1_OVERSTOCK_IMPACT_SCRIPT"
        )
        if configured:
            return Path(configured).expanduser().resolve()
        workspace_gap_script = self._script("task1_gap_analysis.py")
        if workspace_gap_script.exists():
            return workspace_gap_script
        if TASK1_GAP_ANALYSIS_SCRIPT.exists():
            return TASK1_GAP_ANALYSIS_SCRIPT.resolve()
        return self._script("task1_overstock_impact.py")

    def _task1_command(self, action: str) -> list[str]:
        script = self._task1_script()
        command = [self._child_python(), str(script)]
        if action != "--self-test":
            command.append(str(self.output_path))
        command.append(action)
        if (
            self.request.orchestrator_now
            and action != "--self-test"
            and script.name == "task1_gap_analysis.py"
        ):
            command.extend(["--now", self.request.orchestrator_now])
        return command

    def _task2_command(self, action: str = "--write") -> list[str]:
        command = [
            self._child_python(),
            str(self._script("task2_extract_anomalies.py")),
            "--source",
            str(self.output_path),
            action,
        ]
        daily_yield = self._resource_file(DAILY_YIELD_FILENAME, alias="daily_yield")
        if daily_yield:
            command.extend(["--daily-yield", str(daily_yield)])
        if self.request.orchestrator_now:
            command.extend(["--now", self.request.orchestrator_now])
        if self.request.task2_max_anomaly_row is not None:
            command.extend(["--max-anomaly-row", str(self.request.task2_max_anomaly_row)])
        snapshot_dir = self.request.source_files.get("task2_snapshot_dir")
        if snapshot_dir and action == "--write":
            command.extend(["--snapshot-dir", str(snapshot_dir)])
        return command

    def _task3_command(self) -> list[str]:
        command = [
            self._child_python(),
            str(self._script("task3_batch_month_analysis.py")),
            "--source",
            str(self.output_path),
            "--write",
        ]
        batch_yield = self._resource_file(BATCH_YIELD_FILENAME, alias="batch_yield")
        if batch_yield:
            command.extend(["--batch-report", str(batch_yield)])
        daily_yield = self._resource_file(DAILY_YIELD_FILENAME, alias="daily_yield")
        if daily_yield:
            command.extend(["--period-report", str(daily_yield)])
        target = self._target_file()
        if target:
            command.extend(["--target", str(target)])
        return command

    def _task4_command(self) -> list[str]:
        return [
            self._child_python(),
            str(self._script("task4_daily_report_generation.py")),
            "--source",
            str(self.output_path),
            "--write",
        ]

    def _script(self, name: str) -> Path:
        return self.workspace / "scripts" / name

    def _resource_dir(self) -> Path:
        return self.workspace / "resources" / _suffix_from_request(self.request)

    def _resource_file(self, filename: str, *, alias: str) -> Path | None:
        configured = self.request.source_files.get(alias)
        if configured:
            path = Path(configured).expanduser().resolve()
            return path if path.exists() else None
        path = self._resource_dir() / filename
        return path if path.exists() else None

    def _target_file(self) -> Path | None:
        configured = self.request.source_files.get(
            "target_decomposition"
        ) or self.request.source_files.get("target")
        if configured:
            path = Path(configured).expanduser().resolve()
            if path.exists() and _is_standard_xlsx(path):
                return path
        for name in (*DECRYPTED_TARGET_CANDIDATE_NAMES, *TARGET_CANDIDATE_NAMES):
            path = self.workspace / "resources" / name
            if path.exists() and _is_standard_xlsx(path):
                return path
        return None

    def _child_python(self) -> str:
        configured = self.request.source_files.get("child_python") or os.getenv(
            "YIELD_REPORT_CHILD_PYTHON"
        )
        return str(configured or DEFAULT_CHILD_PYTHON)

    def _run_command(
        self,
        child_skill: str,
        command: list[str],
        *,
        timeout: int | None = None,
    ) -> CommandResult:
        try:
            completed = subprocess.run(
                command,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = _decode_timeout_output(exc.stdout)
            stderr = _decode_timeout_output(exc.stderr)
            message = (
                f"{child_skill} timed out after {timeout} seconds; "
                f"continuing because Task0 output workbook already exists: {self.output_path}"
            )
            if stderr:
                message = f"{message}\n{stderr}"
            raise CommandTimeoutError(
                CommandResult(
                    child_skill=child_skill,
                    command=command,
                    returncode=TASK0_TIMEOUT_RETURNCODE,
                    stdout=stdout,
                    stderr=message,
                )
            ) from exc
        result = CommandResult(
            child_skill=child_skill,
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"{child_skill} failed with exit code {completed.returncode}: "
                f"{result.stderr or result.stdout}"
            )
        return result


def _decode_timeout_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return value.strip()


def _cleanup_hidden_excel_processes() -> None:
    if os.name != "nt":
        return
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-Process EXCEL -ErrorAction SilentlyContinue | "
                "Where-Object { -not $_.MainWindowTitle } | "
                "Stop-Process -Force -ErrorAction SilentlyContinue"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _wait_for_file_unlock(path: Path, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with path.open("r+b"):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.5)
    if last_error is not None:
        raise TimeoutError(f"Timed out waiting for workbook lock to clear: {path}") from last_error


def verify_daily_report_workbook(path: Path) -> dict[str, Any]:
    """Verify final Data Packet and upload sheet fields for the full workflow."""
    if not path.exists():
        raise FileNotFoundError(f"Generated workbook does not exist: {path}")

    data_packet_rows = _read_sheet_values(path, DATA_PACKET_SHEET)
    data_header_index, data_headers = _locate_header_row(
        data_packet_rows,
        required=("产品类型",),
    )
    data_table = data_packet_rows[data_header_index:]
    data_col_map = {header: index for index, header in enumerate(data_headers) if header}

    sheet1_name, sheet1_rows = _read_first_available_sheet(path, UPLOAD_SHEET_CANDIDATES)
    sheet1_header_index, sheet1_headers = _locate_header_row(
        sheet1_rows,
        required=("产品类型", "产品", "日期"),
    )
    sheet1_table = sheet1_rows[sheet1_header_index:]
    sheet1_col_map = {header: index for index, header in enumerate(sheet1_headers) if header}
    html_values = _column_values(sheet1_table, _find_column(sheet1_col_map, "当日异常_HTML"))

    return {
        "data_packet": {
            "sheet": DATA_PACKET_SHEET,
            "headers": data_headers,
            "row_count": max(len(data_table) - 1, 0),
            "nonblank_counts": {
                "1.1 过货影响": _count_nonblank_values(
                    data_table, _find_column(data_col_map, "1.1")
                ),
                "1.2 批次分析": _count_nonblank_values(
                    data_table, _find_column(data_col_map, "1.2")
                ),
                "1.3 当日异常": _count_nonblank_values(
                    data_table, _find_column(data_col_map, "1.3")
                ),
                "1.4 已知异常": _count_nonblank_values(
                    data_table, _find_column(data_col_map, "1.4")
                ),
                "月度分析": _count_nonblank_values(
                    data_table, _find_column(data_col_map, "月度分析")
                ),
            },
        },
        "sheet1": {
            "sheet": sheet1_name,
            "headers": sheet1_headers,
            "row_count": max(len(sheet1_table) - 1, 0),
            "nonblank_counts": {
                "当日异常": _count_nonblank_values(
                    sheet1_table, _find_column(sheet1_col_map, "当日异常")
                ),
                "当日异常_HTML": _count_nonblank_values(
                    sheet1_table,
                    _find_column(sheet1_col_map, "当日异常_HTML"),
                ),
                "月度良率说明": _count_nonblank_values(
                    sheet1_table,
                    _find_column(sheet1_col_map, "月度良率说明"),
                ),
            },
            "html_style": _inspect_html_style(html_values),
        },
    }


def _read_first_available_sheet(
    path: Path, sheet_names: tuple[str, ...]
) -> tuple[str, list[list[Any]]]:
    errors: list[str] = []
    for sheet_name in sheet_names:
        try:
            return sheet_name, _read_sheet_values(path, sheet_name)
        except ValueError as exc:
            errors.append(str(exc))
    raise ValueError(f"Workbook missing upload sheet {sheet_names}: {'; '.join(errors)}")


def _locate_header_row(rows: list[list[Any]], required: tuple[str, ...]) -> tuple[int, list[str]]:
    for index, row in enumerate(rows):
        headers = [str(value or "").strip() for value in row]
        if all(
            any(required_header == header for header in headers) for required_header in required
        ):
            return index, headers
    raise ValueError(f"Could not locate header row containing: {', '.join(required)}")


def _column_values(rows: list[list[Any]], col: int | None) -> list[str]:
    if col is None:
        return []
    values: list[str] = []
    for row in rows[1:]:
        if col < len(row):
            text = str(row[col] or "").strip()
            if text:
                values.append(text)
    return values


def _inspect_html_style(html_values: list[str]) -> dict[str, bool]:
    blue_segments = [
        segment
        for value in html_values
        for segment in re.findall(r'<font color="#0000FF">(.*?)</font>', value)
    ]
    return {
        "exception_marker_red_bold": any(
            '<strong><font color="#FF0000">【异常】</font></strong>' in value
            for value in html_values
        ),
        "batch_no_rise_blue": any("批次无上升" in segment for segment in blue_segments),
        "blue_only_for_batch_no_rise": all("批次无上升" in segment for segment in blue_segments),
        "gap_not_blue": all(
            "Gap" not in segment and "GAP" not in segment for segment in blue_segments
        ),
    }


def _is_standard_xlsx(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"PK\x03\x04"
    except OSError:
        return False
