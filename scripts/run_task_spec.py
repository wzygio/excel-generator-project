"""Execute a TaskSpec through the default Agent runtime."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from yield_report.agent.registry import build_default_runtime  # noqa: E402
from yield_report.agent.run_store import RunStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a specs/runs/<run_id>/spec.yaml file")
    parser.add_argument("--spec", required=True, help="Path to spec.yaml.")
    parser.add_argument("--workspace", default=None, help="Project root. Defaults to this repository.")
    args = parser.parse_args(argv)

    workspace = Path(args.workspace).resolve() if args.workspace else PROJECT_ROOT
    spec_path = Path(args.spec)
    store = RunStore(workspace=workspace)
    try:
        spec = store.load_spec(spec_path)
        context = store.make_context(spec_path, spec)
        results = build_default_runtime().run_spec(spec, context)
    except Exception as exc:
        print(f"run failed: {exc}", file=sys.stderr)
        return 1

    for index, result in enumerate(results, start=1):
        status = "succeeded" if result.success else "failed"
        print(f"{index}. {result.skill_name} [{status}] {result.summary}")
    return 0 if results and all(result.success for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
