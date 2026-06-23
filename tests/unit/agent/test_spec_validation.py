from __future__ import annotations

import pytest

from yield_report.agent.spec_model import SkillCall, TaskSpec
from yield_report.agent.spec_validation import SpecValidationError, SpecValidator


def test_spec_validator_accepts_valid_skill_workflow() -> None:
    spec = TaskSpec(
        run_id="agent-data-analysis-20260623-143015",
        status="ready",
        constraints={"spec_source": "agent", "capability": "data-analysis"},
        workflow=[
            SkillCall(id="analyze", skill="data_analysis"),
        ],
        outputs={"analysis_summary": {"required": True}},
        memory={"reuse_policy": "confirmed_only"},
    )

    result = SpecValidator(registered_skills={"data_analysis"}).validate(spec)

    assert result.ok is True
    assert result.errors == []


def test_spec_validator_reports_duplicate_and_unregistered_skill() -> None:
    spec = TaskSpec(
        run_id="agent-data-analysis-20260623-143015",
        constraints={"spec_source": "agent", "capability": "data-analysis"},
        workflow=[
            SkillCall(id="same", skill="data_analysis"),
            SkillCall(id="same", skill="unknown"),
        ],
        outputs={"analysis_summary": {"required": True}},
    )

    result = SpecValidator(registered_skills={"data_analysis"}).validate(spec)

    assert result.ok is False
    assert {issue.code for issue in result.errors} == {
        "spec.workflow.duplicate_id",
        "spec.workflow.unregistered_skill",
    }


def test_spec_validator_rejects_pending_memory_reuse() -> None:
    spec = TaskSpec(
        run_id="agent-data-analysis-20260623-143015",
        constraints={"spec_source": "agent", "capability": "data-analysis"},
        workflow=[SkillCall(id="analyze", skill="data_analysis")],
        outputs={"analysis_summary": {"required": True}},
        memory={"reuse_policy": "pending_allowed"},
    )

    with pytest.raises(SpecValidationError):
        SpecValidator(registered_skills={"data_analysis"}).assert_valid(spec)


def test_spec_validator_rejects_legacy_run_id() -> None:
    spec = TaskSpec(
        run_id="run-20260623-143015",
        constraints={"spec_source": "agent", "capability": "data-analysis"},
        workflow=[SkillCall(id="analyze", skill="data_analysis")],
        outputs={"analysis_summary": {"required": True}},
    )

    result = SpecValidator(registered_skills={"data_analysis"}).validate(spec)

    assert "spec.run_id.invalid" in {issue.code for issue in result.errors}


def test_spec_validator_requires_spec_source_and_capability() -> None:
    spec = TaskSpec(
        run_id="agent-data-analysis-20260623-143015",
        workflow=[SkillCall(id="analyze", skill="data_analysis")],
        outputs={"analysis_summary": {"required": True}},
    )

    result = SpecValidator(registered_skills={"data_analysis"}).validate(spec)

    assert {
        "spec.constraints.spec_source_missing",
        "spec.constraints.capability_missing",
    }.issubset({issue.code for issue in result.errors})
