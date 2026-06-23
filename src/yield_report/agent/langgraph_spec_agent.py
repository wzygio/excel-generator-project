"""LangGraph-backed Spec construction sub-agent."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

import yaml
from langgraph.graph import END, START, StateGraph

from yield_report.agent.run_id import RunIdFactory, normalize_capability, normalize_source
from yield_report.agent.spec_model import TaskSpec
from yield_report.agent.spec_validation import SpecValidationIssue, validate_task_spec

if TYPE_CHECKING:
    from yield_report.agent.spec_builder import SpecBuildRequest

DraftGenerator = Callable[[Any, list[SpecValidationIssue], str], dict[str, Any] | str]


class SpecAgentResult(TypedDict):
    spec: TaskSpec
    warnings: list[str]
    validation_issues: list[SpecValidationIssue]


class SpecAgentState(TypedDict):
    request: Any
    context: NotRequired[str]
    raw_spec: NotRequired[dict[str, Any] | str]
    spec: NotRequired[TaskSpec]
    warnings: NotRequired[list[str]]
    validation_issues: NotRequired[list[SpecValidationIssue]]
    repair_attempts: NotRequired[int]


class LangGraphSpecAgent:
    """Generate, validate, and repair TaskSpecs through a LangGraph state machine."""

    def __init__(
        self,
        *,
        workspace: Path,
        draft_generator: DraftGenerator,
        registered_skills: set[str],
        today_clock: Callable[[], Any],
        max_repair_attempts: int = 2,
    ) -> None:
        self.workspace = workspace
        self._draft_generator = draft_generator
        self._registered_skills = registered_skills
        self._run_id_factory = RunIdFactory(clock=today_clock)
        self._max_repair_attempts = max_repair_attempts
        self._graph = self._compile_graph()

    def build(self, request: SpecBuildRequest) -> SpecAgentResult:
        state = self._graph.invoke(
            {
                "request": request,
                "warnings": [],
                "validation_issues": [],
                "repair_attempts": 0,
            }
        )
        spec = state.get("spec")
        if not isinstance(spec, TaskSpec):
            spec = self._fallback_spec(request, state.get("validation_issues", []))
        return {
            "spec": spec,
            "warnings": state.get("warnings", []),
            "validation_issues": state.get("validation_issues", []),
        }

    def _compile_graph(self):
        graph = StateGraph(SpecAgentState)
        graph.add_node("load_context", self._load_context)
        graph.add_node("generate_draft", self._generate_draft)
        graph.add_node("parse_validate", self._parse_validate)
        graph.add_node("repair", self._repair)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "load_context")
        graph.add_edge("load_context", "generate_draft")
        graph.add_edge("generate_draft", "parse_validate")
        graph.add_conditional_edges(
            "parse_validate",
            self._next_after_validation,
            {"repair": "repair", "finalize": "finalize"},
        )
        graph.add_edge("repair", "parse_validate")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _load_context(self, state: SpecAgentState) -> dict[str, Any]:
        parts: list[str] = []
        for relative in [
            "docs/agent/spec_contract.md",
            "docs/agent/skill_contract.md",
            "specs/templates/daily_report_spec.yaml",
            "specs/templates/anomaly_monitor_spec.yaml",
        ]:
            path = self.workspace / relative
            if path.exists():
                parts.append(f"# {relative}\n{path.read_text(encoding='utf-8')}")
        return {"context": "\n\n".join(parts)}

    def _generate_draft(self, state: SpecAgentState) -> dict[str, Any]:
        request = state["request"]
        issues = state.get("validation_issues", [])
        context = state.get("context", "")
        try:
            raw = self._draft_generator(request, issues, context)
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

    def _parse_validate(self, state: SpecAgentState) -> dict[str, Any]:
        request = state["request"]
        try:
            spec = _parse_raw_spec(state.get("raw_spec"))
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
                registered_skills=self._registered_skills,
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

    def _next_after_validation(self, state: SpecAgentState) -> str:
        errors = [issue for issue in state.get("validation_issues", []) if issue.severity == "error"]
        if errors and state.get("repair_attempts", 0) < self._max_repair_attempts:
            return "repair"
        return "finalize"

    def _repair(self, state: SpecAgentState) -> dict[str, Any]:
        request = state["request"]
        issues = state.get("validation_issues", [])
        context = state.get("context", "")
        repair_attempts = state.get("repair_attempts", 0) + 1
        try:
            raw = self._draft_generator(request, issues, context)
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

    def _finalize(self, state: SpecAgentState) -> dict[str, Any]:
        spec = state.get("spec")
        issues = state.get("validation_issues", [])
        errors = [issue for issue in issues if issue.severity == "error"]
        if isinstance(spec, TaskSpec) and errors:
            spec.status = "needs_confirmation"
            return {"spec": spec}
        if not isinstance(spec, TaskSpec):
            return {"spec": self._fallback_spec(state["request"], issues)}
        return {}

    def _resolve_run_id(self, request: SpecBuildRequest, source: str, capability: str) -> str:
        if request.run_id:
            RunIdFactory.validate(request.run_id)
            return request.run_id
        return self._run_id_factory.create(source=source, capability=capability)

    @staticmethod
    def _resolve_capability(request: SpecBuildRequest, spec: TaskSpec) -> str:
        raw = request.capability or spec.constraints.get("capability") or _infer_capability(spec)
        return normalize_capability(str(raw))

    def _fallback_spec(
        self,
        request: SpecBuildRequest,
        issues: list[SpecValidationIssue],
    ) -> TaskSpec:
        capability = normalize_capability(request.capability or "data-analysis")
        source = normalize_source(request.source)
        run_id = request.run_id or self._run_id_factory.create(
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


def _parse_raw_spec(raw: dict[str, Any] | str | None) -> TaskSpec:
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


def _infer_capability(spec: TaskSpec) -> str:
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
