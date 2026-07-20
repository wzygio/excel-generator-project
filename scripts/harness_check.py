from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECK_CONFIG = json.loads(r'''{
  "required_headings": [
    "Project Overview",
    "Code Intelligence Policy",
    "Context Router",
    "Iteration Router",
    "Agent skills",
    "Safety Boundary"
  ],
  "allow_additional_headings": true,
  "index_policy": "folder-only",
  "architecture_max_path_depth": 2,
  "required_paths": [
    "AGENTS.md",
    "ARCHITECTURE.md",
    "CONTEXT.md",
    ".scratch",
    ".planning",
    "docs/PRD",
    "docs/ADR",
    "references/index.md",
    "references/design_references/index.md",
    "references/design_references/domain/GLOSSARY.md",
    "references/dev_references/index.md",
    "references/test_references/index.md",
    "references/summary_references/index.md",
    "references/retrospective.md",
    "docs/agents/issue-tracker.md",
    "docs/agents/triage-labels.md",
    "docs/agents/domain.md",
    "scripts/harness_check.py"
  ],
  "agents_path": "AGENTS.md",
  "architecture_path": "ARCHITECTURE.md",
  "references_root": "references",
  "legacy_archive": "references/generated/legacy-harness",
  "default_audit_path": "references/generated/harness-check.json",
  "profile_id": "agent-workflow-v1"
}''')


def _referenced_paths(markdown: str) -> list[str]:
    link_targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)
    code_paths = re.findall(r"`([^`]+)`", markdown)
    return link_targets + code_paths


def _check_agents_router() -> dict[str, Any]:
    agents_path = PROJECT_ROOT / CHECK_CONFIG["agents_path"]
    agents = agents_path.read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", agents, flags=re.MULTILINE)
    expected = CHECK_CONFIG["required_headings"]
    missing = [heading for heading in expected if heading not in headings]
    positions = [headings.index(heading) for heading in expected if heading in headings]
    violations = [f"missing heading: {heading}" for heading in missing]
    if positions != sorted(positions):
        violations.append(f"required headings out of order: {headings}")
    if not CHECK_CONFIG.get("allow_additional_headings", True) and headings != expected:
        violations.append(f"unexpected headings: {headings}")
    if f"{CHECK_CONFIG['references_root']}/" not in agents:
        violations.append("missing references router")
    return {"status": "ok" if not violations else "failed", "violations": violations}


def _check_folder_only_indexes() -> dict[str, Any]:
    if CHECK_CONFIG.get("index_policy") != "folder-only":
        return {"status": "skipped", "index_count": 0, "violations": []}

    references_root = PROJECT_ROOT / CHECK_CONFIG["references_root"]
    legacy_archive = PROJECT_ROOT / CHECK_CONFIG["legacy_archive"]
    index_files = [
        path
        for path in sorted(references_root.rglob("index.md"))
        if legacy_archive != path and legacy_archive not in path.parents
    ]
    violations: list[str] = []
    for index_file in index_files:
        markdown = index_file.read_text(encoding="utf-8")
        for raw_path in _referenced_paths(markdown):
            path = raw_path.strip().replace("\\", "/").rstrip("/")
            if not path or path.startswith(("http://", "https://", "#")):
                continue
            if any(char in path for char in "*?"):
                continue
            if not path.startswith(f"{CHECK_CONFIG['references_root']}/"):
                continue
            candidate = PurePosixPath(path)
            if candidate.suffix:
                violations.append(f"{index_file.relative_to(PROJECT_ROOT)} -> file route: {path}")
                continue
            if not (PROJECT_ROOT / path).is_dir():
                violations.append(f"{index_file.relative_to(PROJECT_ROOT)} -> missing folder: {path}")
    return {
        "status": "ok" if not violations else "failed",
        "index_count": len(index_files),
        "violations": violations,
    }


def _check_architecture_depth() -> dict[str, Any]:
    architecture = (PROJECT_ROOT / CHECK_CONFIG["architecture_path"]).read_text(encoding="utf-8")
    max_depth = int(CHECK_CONFIG.get("architecture_max_path_depth", 2))
    project_roots = {
        path.name
        for path in PROJECT_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }
    deep_paths = sorted(
        {
            match.group(0).rstrip("/")
            for match in re.finditer(
                r"(?<![\w./-])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+/?",
                architecture,
            )
            if "://" not in match.group(0)
            and match.group(0).split("/", 1)[0] in project_roots
            and len(PurePosixPath(match.group(0).rstrip("/")).parts) > max_depth
        }
    )
    return {"status": "ok" if not deep_paths else "failed", "violations": deep_paths}


def _check_required_harness_paths() -> dict[str, Any]:
    missing = [path for path in CHECK_CONFIG["required_paths"] if not (PROJECT_ROOT / path).exists()]
    return {"status": "ok" if not missing else "failed", "missing": missing}


def run_checks() -> dict[str, Any]:
    checks = {
        "agents_router": _check_agents_router(),
        "folder_only_indexes": _check_folder_only_indexes(),
        "architecture_depth": _check_architecture_depth(),
        "required_harness_paths": _check_required_harness_paths(),
    }
    passed = all(check["status"] in {"ok", "skipped"} for check in checks.values())
    return {
        "status": "ok" if passed else "failed",
        "profile_id": CHECK_CONFIG["profile_id"],
        "checks": checks,
    }


def _write_audit(payload: dict[str, Any], audit_path: Path) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the profile-driven project Harness.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--write-audit",
        nargs="?",
        const=CHECK_CONFIG["default_audit_path"],
        help="Write the check result to the configured or supplied path.",
    )
    args = parser.parse_args()

    payload = run_checks()
    if args.write_audit:
        _write_audit(payload, PROJECT_ROOT / args.write_audit)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Harness status: {payload['status']} ({payload['profile_id']})")
        for name, check in payload["checks"].items():
            print(f"- {name}: {check['status']}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
