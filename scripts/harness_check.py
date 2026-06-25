from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_AGENTS_HEADINGS = [
    "Project Overview",
    "Code Intelligence Policy",
    "Context Router",
    "Iteration Router",
    "Safety Boundary",
]
REQUIRED_HARNESS_PATHS = [
    "AGENTS.md",
    "ARCHITECTURE.md",
    "references/index.md",
    "references/design/index.md",
    "references/dev_references/index.md",
    "references/test_references/index.md",
    "references/retrospective.md",
]


def _referenced_paths(markdown: str) -> list[str]:
    link_targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)
    code_paths = re.findall(r"`([^`]*(?:references|ARCHITECTURE\.md)[^`]*)`", markdown)
    plain_reference_paths = re.findall(
        r"(?<![\w/.-])(?:\.\./)*(?:references|ARCHITECTURE\.md)[\w./*-]*",
        markdown,
    )
    return link_targets + code_paths + plain_reference_paths


def _check_agents_router() -> dict[str, Any]:
    agents_path = PROJECT_ROOT / "AGENTS.md"
    agents = agents_path.read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", agents, flags=re.MULTILINE)
    forbidden = [
        "## Commands",
        "## Coding Conventions",
        "## Validation",
        "## Rules Boundary",
        "## Source Of Truth",
    ]
    violations = [heading for heading in forbidden if heading in agents]
    if headings != EXPECTED_AGENTS_HEADINGS:
        violations.append(f"unexpected headings: {headings}")
    if "references/" not in agents:
        violations.append("missing references router")
    return {"status": "ok" if not violations else "failed", "violations": violations}


def _check_folder_only_indexes() -> dict[str, Any]:
    legacy_archive = PROJECT_ROOT / "references" / "generated" / "legacy-harness"
    index_files = [
        path
        for path in sorted((PROJECT_ROOT / "references").rglob("index.md"))
        if legacy_archive not in path.parents
    ]
    violations: list[str] = []
    for index_file in index_files:
        markdown = index_file.read_text(encoding="utf-8")
        for raw_path in _referenced_paths(markdown):
            path = raw_path.strip()
            if not path or path.startswith(("http://", "https://", "#")):
                continue
            if any(char in path for char in "*?"):
                continue
            if Path(path).suffix:
                violations.append(f"{index_file.relative_to(PROJECT_ROOT)} -> {path}")
                continue
            if path.startswith("references/") and not (PROJECT_ROOT / path).is_dir():
                violations.append(f"missing folder: {path}")
    return {
        "status": "ok" if not violations else "failed",
        "index_count": len(index_files),
        "violations": violations,
    }


def _check_architecture_depth() -> dict[str, Any]:
    architecture = (PROJECT_ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    project_roots = {
        path.name
        for path in PROJECT_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }
    deep_paths = sorted(
        {
            match.group(0).rstrip("/")
            for match in re.finditer(
                r"(?<![\w./-])(?:[A-Za-z0-9_.-]+/){2,}[A-Za-z0-9_.-]+/?",
                architecture,
            )
            if "://" not in match.group(0)
            and match.group(0).split("/", 1)[0] in project_roots
        }
    )
    return {"status": "ok" if not deep_paths else "failed", "violations": deep_paths}


def _check_required_harness_paths() -> dict[str, Any]:
    missing = [path for path in REQUIRED_HARNESS_PATHS if not (PROJECT_ROOT / path).exists()]
    return {"status": "ok" if not missing else "failed", "missing": missing}


def run_checks() -> dict[str, Any]:
    checks = {
        "agents_router": _check_agents_router(),
        "folder_only_indexes": _check_folder_only_indexes(),
        "architecture_depth": _check_architecture_depth(),
        "required_harness_paths": _check_required_harness_paths(),
    }
    status = "ok" if all(check["status"] == "ok" for check in checks.values()) else "failed"
    return {"status": status, "checks": checks}


def _write_audit(payload: dict[str, Any], audit_path: Path) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the lightweight project Harness.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--write-audit",
        nargs="?",
        const="references/generated/harness-check.json",
        help="Write the check result to the given path.",
    )
    args = parser.parse_args()

    payload = run_checks()
    if args.write_audit:
        _write_audit(payload, PROJECT_ROOT / args.write_audit)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Harness status: {payload['status']}")
        for name, check in payload["checks"].items():
            print(f"- {name}: {check['status']}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
