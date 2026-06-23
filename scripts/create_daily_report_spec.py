"""Create a daily-report TaskSpec from a natural-language goal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

from yield_report.agent.run_store import RunStore  # noqa: E402
from yield_report.agent.spec_builder import SpecBuilder, SpecBuildRequest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create specs/runs/<run_id>/spec.yaml")
    parser.add_argument("--goal", required=True, help="Natural-language daily-report goal.")
    parser.add_argument("--run-id", default=None, help="Optional stable run id.")
    parser.add_argument("--source", default="agent", help="Run id source segment.")
    parser.add_argument("--capability", default="daily_report", help="Capability segment.")
    parser.add_argument(
        "--fixed-flow",
        action="store_true",
        default=True,
        help="Use the fixed daily_report business flow.",
    )
    parser.add_argument("--workspace", default=None, help="Project root. Defaults to this repository.")
    parser.add_argument("--report-date", default=None, help="Optional YYYY-MM-DD report date override.")
    parser.add_argument("--product-model", action="append", default=None, help="Product model override.")
    parser.add_argument("--section", action="append", default=None, help="Daily-report section override.")
    parser.add_argument(
        "--builder-mode",
        default="auto",
        choices=["auto", "llm", "auto_llm"],
        help="SpecBuilder mode. auto is deterministic; llm attempts LLM conversion first.",
    )
    parser.add_argument("--print-path", action="store_true", help="Print only the generated spec path.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable build payload.")
    args = parser.parse_args(argv)

    workspace = Path(args.workspace).resolve() if args.workspace else PROJECT_ROOT
    store = RunStore(workspace=workspace)
    result = SpecBuilder(store=store).build(
        SpecBuildRequest(
            user_goal=args.goal,
            run_id=args.run_id,
            source=args.source,
            capability=args.capability,
            fixed_flow=args.fixed_flow,
            report_date=args.report_date,
            product_models=args.product_model,
            sections=args.section or [],
            builder_mode=args.builder_mode,
        )
    )
    display_path = _display_path(result.spec_path, workspace)
    if args.json:
        print(
            json.dumps(
                {
                    "success": not result.validation_issues or not any(
                        issue.severity == "error" for issue in result.validation_issues
                    ),
                    "run_id": result.paths.run_id,
                    "spec_path": display_path,
                    "status": result.spec.status,
                    "warnings": result.warnings,
                    "validation_issues": [
                        issue.model_dump(mode="json") for issue in result.validation_issues
                    ],
                    "spec": result.spec.model_dump(mode="json"),
                },
                ensure_ascii=False,
            )
        )
    elif args.print_path:
        print(display_path)
    else:
        print(f"spec_path: {display_path}")
        print(f"status: {result.spec.status}")
        for warning in result.warnings:
            print(f"warning: {warning}")
    return 0


def _display_path(path: Path, workspace: Path) -> str:
    try:
        return str(path.relative_to(workspace))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
