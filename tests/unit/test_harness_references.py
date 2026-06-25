from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _referenced_paths(markdown: str) -> list[str]:
    link_targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)
    code_paths = re.findall(r"`([^`]*(?:references|ARCHITECTURE\.md)[^`]*)`", markdown)
    plain_reference_paths = re.findall(
        r"(?<![\w/.-])(?:\.\./)*(?:references|ARCHITECTURE\.md)[\w./*-]*",
        markdown,
    )
    return link_targets + code_paths + plain_reference_paths


def test_harness_indexes_route_to_folders_not_files() -> None:
    """Harness indexes should stay cheap to maintain by routing only to folders."""
    index_files = sorted((PROJECT_ROOT / "references").rglob("index.md"))

    assert index_files, "references should contain Harness index.md files"

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

    assert violations == []


def test_harness_indexes_explain_read_guidance_and_commands() -> None:
    """Every Harness index should say when to read it and what command surface applies."""
    index_files = sorted((PROJECT_ROOT / "references").rglob("index.md"))

    assert index_files, "references should contain Harness index.md files"

    violations: list[str] = []
    for index_file in index_files:
        markdown = index_file.read_text(encoding="utf-8")
        if "When To Read" not in markdown and "Read Guidance" not in markdown:
            violations.append(f"{index_file.relative_to(PROJECT_ROOT)} missing read guidance")
        if "Commands" not in markdown:
            violations.append(f"{index_file.relative_to(PROJECT_ROOT)} missing commands guidance")

    assert violations == []


def test_architecture_stays_at_second_level_project_paths() -> None:
    """The root architecture map should stay shallow and delegate deep lookup."""
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

    assert deep_paths == []


def test_agents_md_is_stable_context_and_iteration_router() -> None:
    """Root AGENTS.md should route to Harness references instead of storing details."""
    agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", agents, flags=re.MULTILINE)

    assert headings == [
        "Project Overview",
        "Code Intelligence Policy",
        "Context Router",
        "Iteration Router",
        "Safety Boundary",
    ]
    assert "references/" in agents
    assert "## Commands" not in agents
    assert "## Coding Conventions" not in agents
    assert "## Validation" not in agents
    assert "## Rules Boundary" not in agents
    assert "## Source Of Truth" not in agents


def test_harness_check_script_reports_clean_harness() -> None:
    """The Harness should expose a runnable local verification command."""
    script = PROJECT_ROOT / "scripts" / "harness_check.py"

    result = subprocess.run(
        [sys.executable, str(script), "--json"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert {
        "agents_router",
        "folder_only_indexes",
        "architecture_depth",
        "required_harness_paths",
    }.issubset(set(payload["checks"]))
