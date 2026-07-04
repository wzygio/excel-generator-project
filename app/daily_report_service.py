"""Service layer for the standalone daily report Streamlit UI."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from yield_report.agent.spec_model import RunContext, SkillResult
from yield_report.skills.daily_report import tool as daily_report_tool
from yield_report.skills.daily_report.models import DailyReportRequest

DEFAULT_REPORT_OUTPUT_DIR = Path("output") / "artifacts" / "reports" / "generated"

DailyReportRunner = Callable[[DailyReportRequest, RunContext], SkillResult]


@dataclass(frozen=True)
class DailyReportFormInput:
    """User-entered values for one daily report generation run."""

    report_date: str | None = None
    generator_workspace: Path | None = None
    generator_root: Path | None = None
    output_dir: Path | None = None
    generator_now: str | None = None


@dataclass(frozen=True)
class DownloadableReport:
    """One file that the Streamlit UI can expose as a download."""

    path: Path
    label: str
    kind: str = "excel"
    size_bytes: int = 0


@dataclass(frozen=True)
class DailyReportRunView:
    """Presentation-friendly result returned to the Streamlit UI."""

    success: bool
    summary: str
    output_file: Path | None = None
    downloads: list[DownloadableReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    workflow: list[str] = field(default_factory=list)
    error_message: str = ""
    raw_result: SkillResult | None = None


def generate_daily_report(
    form: DailyReportFormInput,
    *,
    workspace: Path,
    runner: DailyReportRunner = daily_report_tool.run,
    preflight: bool = True,
) -> DailyReportRunView:
    """Generate a daily report through the project daily_report skill."""
    workspace = Path(workspace).resolve()
    output_dir = _resolve_output_dir(form, workspace)
    output_dir.mkdir(parents=True, exist_ok=True)

    if preflight:
        errors = _preflight_errors(workspace)
        if errors:
            return DailyReportRunView(
                success=False,
                summary="运行环境预检失败",
                warnings=errors,
                error_message="\n".join(errors),
            )

    source_files: dict[str, Path] = {}
    if form.generator_root is not None:
        source_files["daily_report_generator_root"] = Path(form.generator_root)

    request = DailyReportRequest(
        report_date=form.report_date or None,
        generator_workspace=form.generator_workspace or workspace,
        generator_now=form.generator_now,
        output_dir=output_dir,
        source_files=source_files,
    )
    context = RunContext(
        run_id=_run_id(form),
        workspace=workspace,
        output_dir=Path("output"),
    )
    result = runner(request, context)
    output_file = _result_output_file(result)
    downloads = _downloads_from_result(result, output_file)
    error_message = result.error.message if result.error else ""
    workflow = result.data.get("workflow")

    return DailyReportRunView(
        success=result.success,
        summary=result.summary,
        output_file=output_file,
        downloads=downloads,
        warnings=list(result.warnings),
        workflow=[str(item) for item in workflow] if isinstance(workflow, list) else [],
        error_message=error_message,
        raw_result=result,
    )


def list_generated_reports(
    output_dir: Path | str | None = None,
    *,
    workspace: Path,
    limit: int = 10,
) -> list[DownloadableReport]:
    """Return recent generated Excel reports from the configured output directory."""
    base_dir = Path(output_dir or DEFAULT_REPORT_OUTPUT_DIR).expanduser()
    if not base_dir.is_absolute():
        base_dir = Path(workspace).resolve() / base_dir
    if not base_dir.exists():
        return []

    reports: list[Path] = []
    for path in base_dir.glob("*.xlsx"):
        if path.name.startswith("~$") or not path.is_file():
            continue
        reports.append(path)

    reports.sort(key=lambda item: (item.stat().st_mtime_ns, item.name), reverse=True)
    return [
        DownloadableReport(path=path, label=path.name, size_bytes=path.stat().st_size)
        for path in reports[:limit]
    ]


def _preflight_errors(workspace: Path) -> list[str]:
    errors: list[str] = []
    missing_modules = [
        module_name
        for module_name in ("sqlalchemy", "psycopg2")
        if importlib.util.find_spec(module_name) is None
    ]
    if missing_modules:
        errors.append(
            "缺少日报生成依赖: "
            + ", ".join(missing_modules)
            + "。请先执行 `uv sync` 或安装项目依赖。"
        )

    resources_dir = workspace / "resources"
    target_candidates = list(resources_dir.glob("*目标*.xlsx")) if resources_dir.exists() else []
    target_candidates = [
        path
        for path in target_candidates
        if path.is_file() and not path.name.startswith("~$")
    ]
    if not target_candidates:
        errors.append("缺少目标表: 请将 `26年目标.xlsx` 放到当前 repo 的 `resources` 目录下。")
    return errors


def _resolve_output_dir(form: DailyReportFormInput, workspace: Path) -> Path:
    output_dir = form.output_dir or DEFAULT_REPORT_OUTPUT_DIR
    output_dir = Path(output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = workspace / output_dir
    return output_dir


def _result_output_file(result: SkillResult) -> Path | None:
    output = result.data.get("output_file")
    if isinstance(output, str) and output:
        return Path(output)
    for artifact in result.artifacts:
        if artifact.kind == "excel":
            return Path(artifact.path)
    return None


def _downloads_from_result(
    result: SkillResult,
    output_file: Path | None,
) -> list[DownloadableReport]:
    downloads: list[DownloadableReport] = []
    seen: set[Path] = set()
    candidates = [Path(artifact.path) for artifact in result.artifacts if artifact.kind == "excel"]
    if output_file is not None:
        candidates.insert(0, output_file)
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not path.exists() or not path.is_file():
            continue
        seen.add(resolved)
        downloads.append(
            DownloadableReport(
                path=path,
                label=path.name,
                size_bytes=path.stat().st_size,
            )
        )
    return downloads


def _run_id(form: DailyReportFormInput) -> str:
    suffix = (form.report_date or "latest").replace("-", "")
    return f"streamlit-daily-report-{suffix}"
