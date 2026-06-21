"""Execute a TaskSpec through the default Agent runtime."""

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
from yield_report.agent.runtime_adapter import RuntimeRouter  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a specs/runs/<run_id>/spec.yaml file")
    parser.add_argument("--spec", required=True, help="Path to spec.yaml.")
    parser.add_argument("--workspace", default=None, help="Project root. Defaults to this repository.")
    parser.add_argument(
        "--runtime",
        default="auto",
        choices=["auto", "python", "letta", "omp", "pi"],
        help=(
            "Runtime to use. auto follows config/default runtime; letta uses the "
            "stateful Letta Agent Runtime."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable run payload.")
    args = parser.parse_args(argv)

    workspace = Path(args.workspace).resolve() if args.workspace else PROJECT_ROOT
    spec_path = Path(args.spec)
    store = RunStore(workspace=workspace)
    try:
        spec = store.load_spec(spec_path)
        context = store.make_context(spec_path, spec)
        run_result = RuntimeRouter().run_spec(
            spec,
            context,
            requested_runtime=args.runtime,
        )
        results = run_result.results
    except Exception as exc:
        if args.json:
            print(
                json.dumps(
                    {"success": False, "summary": f"run failed: {exc}"},
                    ensure_ascii=False,
                )
            )
        else:
            print(f"run failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "success": run_result.success,
                    "runtime": run_result.runtime,
                    "status": run_result.status,
                    "summary": run_result.summary,
                    "results": [result.model_dump(mode="json") for result in results],
                },
                ensure_ascii=False,
            )
        )
        return 0 if run_result.success else 1

    for index, result in enumerate(results, start=1):
        status = "succeeded" if result.success else "failed"
        print(f"{index}. {result.skill_name} [{status}] {result.summary}")
    return 0 if run_result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
