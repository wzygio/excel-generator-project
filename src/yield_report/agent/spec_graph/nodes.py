"""Node functions for the LangGraph Spec sub-agent."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import yaml

from yield_report.agent.run_id import normalize_capability, normalize_source
from yield_report.agent.spec_graph.state import SpecAgentState, SpecGraphDeps
from yield_report.agent.spec_model import TaskSpec
from yield_report.agent.spec_validation import SpecValidationIssue, validate_task_spec

if TYPE_CHECKING:
    from yield_report.agent.spec_builder import SpecBuildRequest


class SpecGraphNodes:
    """LangGraph node handlers for TaskSpec construction."""

    def __init__(self, deps: SpecGraphDeps) -> None:
        self.deps = deps

    def load_context(self, state: SpecAgentState) -> dict[str, Any]:
        del state
        parts: list[str] = []
        for relative in [
            "docs/agent/spec_contract.md",
            "docs/agent/skill_contract.md",
            "specs/templates/daily_report_spec.yaml",
            "specs/templates/anomaly_monitor_spec.yaml",
        ]:
            path = self.deps.workspace / relative
            if path.exists():
                parts.append(f"# {relative}\n{path.read_text(encoding='utf-8')}")
        return {"context": "\n\n".join(parts)}

    def generate_draft(self, state: SpecAgentState) -> dict[str, Any]:
        request = state["request"]
        issues = state.get("validation_issues", [])
        context = state.get("context", "")
        try:
            raw = self.deps.draft_generator(request, issues, context)
        except Exception as exc:
            return {
                "validation_issues": [
                    SpecValidationIssue(
                        code="spec.llm.generation_failed",
                        message=str(exc),
                        location="llm",
                    )
                ],
                "warnings": [f"LangGraph Spec draft generation failed: {exc}"],
            }
        return {"raw_spec": raw}

    def parse_validate(self, state: SpecAgentState) -> dict[str, Any]:
        request = state["request"]
        try:
            spec = parse_raw_spec(state.get("raw_spec"))
            capability = self._resolve_capability(request, spec)
            source = normalize_source(request.source)
            spec.run_id = self._resolve_run_id(request, source, capability)
            spec.constraints.update(
                {
                    "spec_source": source,
                    "spec_builder": "langgraph",
                    "builder_mode": "langgraph",
                    "capability": capability,
                    "codex_in_execution_chain": False,
                }
            )
            if spec.status in {"", "draft"}:
                spec.status = "ready"
            validation = validate_task_spec(
                spec,
                registered_skills=self.deps.registered_skills,
            )
            return {"spec": spec, "validation_issues": validation.issues}
        except Exception as exc:
            return {
                "validation_issues": [
                    SpecValidationIssue(
                        code="spec.llm.parse_or_validate_failed",
                        message=str(exc),
                        location="llm",
                    )
                ]
            }

    def repair(self, state: SpecAgentState) -> dict[str, Any]:
        request = state["request"]
        issues = state.get("validation_issues", [])
        context = state.get("context", "")
        repair_attempts = state.get("repair_attempts", 0) + 1
        try:
            raw = self.deps.draft_generator(request, issues, context)
        except Exception as exc:
            return {
                "repair_attempts": repair_attempts,
                "validation_issues": [
                    SpecValidationIssue(
                        code="spec.llm.repair_failed",
                        message=str(exc),
                        location="llm",
                    )
                ],
                "warnings": [f"LangGraph Spec repair failed: {exc}"],
            }
        return {
            "raw_spec": raw,
            "repair_attempts": repair_attempts,
            "warnings": [f"LangGraph Spec repaired draft after validation failure #{repair_attempts}"],
        }

    def finalize(self, state: SpecAgentState) -> dict[str, Any]:
        spec = state.get("spec")
        issues = state.get("validation_issues", [])
        errors = [issue for issue in issues if issue.severity == "error"]
        if isinstance(spec, TaskSpec) and errors:
            spec.status = "needs_confirmation"
            return {"spec": spec}
        if not isinstance(spec, TaskSpec):
            return {"spec": self.fallback_spec(state["request"], issues)}
        return {}

    def fallback_spec(
        self,
        request: SpecBuildRequest,
        issues: list[SpecValidationIssue],
    ) -> TaskSpec:
        del issues
        capability = normalize_capability(request.capability or "data-analysis")
        source = normalize_source(request.source)
        run_id = request.run_id or self.deps.run_id_factory.create(
            source=source,
            capability=capability,
        )
        return TaskSpec(
            run_id=run_id,
            status="needs_confirmation",
            user_goal=request.user_goal,
            constraints={
                "spec_source": source,
                "spec_builder": "langgraph",
                "builder_mode": "langgraph",
                "capability": capability,
                "codex_in_execution_chain": False,
            },
            outputs={"trace": {"required": True, "format": "jsonl"}},
            memory={"reuse_policy": "confirmed_only", "candidate_policy": "record_pending"},
            trace={"path": "trace.jsonl"},
        )

    def _resolve_run_id(self, request: SpecBuildRequest, source: str, capability: str) -> str:
        if request.run_id:
            self.deps.run_id_factory.validate(request.run_id)
            return request.run_id
        return self.deps.run_id_factory.create(source=source, capability=capability)

    @staticmethod
    def _resolve_capability(request: SpecBuildRequest, spec: TaskSpec) -> str:
        raw = request.capability or spec.constraints.get("capability") or infer_capability(spec)
        return normalize_capability(str(raw))


def parse_raw_spec(raw: dict[str, Any] | str | None) -> TaskSpec:
    """Parse an LLM draft into a TaskSpec."""

    if isinstance(raw, dict):
        return TaskSpec(**raw)
    if not isinstance(raw, str):
        raise ValueError("LLM Spec output is empty")
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|yaml)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return TaskSpec(**json.loads(text))
    except json.JSONDecodeError:
        loaded = yaml.safe_load(text)
        if not isinstance(loaded, dict):
            raise ValueError("LLM Spec output is not a JSON/YAML mapping")
        return TaskSpec(**loaded)


def infer_capability(spec: TaskSpec) -> str:
    """Infer capability from workflow skills when the draft omitted it."""

    skills = [call.skill for call in spec.workflow]
    if "daily_report" in skills:
        return "daily-report"
    if "anomaly_monitor" in skills:
        return "anomaly-monitor"
    if "report_download" in skills:
        return "report-download"
    if "data_analysis" in skills:
        return "data-analysis"
    return "data-analysis"
