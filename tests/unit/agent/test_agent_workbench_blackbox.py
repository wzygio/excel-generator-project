from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook

from scripts import agent_workbench_bridge

BLACKBOX_GOAL = "请分析M678最近三个月的月度良率变化趋势；如果有恶化，请给出恶化原因"


def test_workbench_letta_agent_executes_m678_monthly_trend_blackbox(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_daily_yield_fixture(
        tmp_path / "resources" / "V3良率及不良率By月周天汇总报表.xlsx"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LETTA_API_KEY", "test-key")
    monkeypatch.setenv("LETTA_AGENT_ID", "agent-blackbox-test")

    class FakeMessages:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return SimpleNamespace(
                    messages=[
                        SimpleNamespace(
                            message_type="approval_request_message",
                            tool_call=SimpleNamespace(
                                name="yield_data_analysis",
                                arguments=json.dumps(
                                    {
                                        "analysis_goal": BLACKBOX_GOAL,
                                        "product_models": ["M678"],
                                        "metrics": ["月度良率"],
                                        "time_grain": "monthly",
                                        "requested_periods": 3,
                                    },
                                    ensure_ascii=False,
                                ),
                                tool_call_id="call-m678-monthly-trend",
                            ),
                        )
                    ],
                    run_id="letta-run-first",
                )
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="已完成 M678 最近三个月月度良率趋势分析。",
                    )
                ],
                run_id="letta-run-final",
            )

    fake_messages = FakeMessages()

    class FakeLetta:
        def __init__(self, **kwargs) -> None:
            self.agents = SimpleNamespace(messages=fake_messages)

    monkeypatch.setitem(sys.modules, "letta_client", SimpleNamespace(Letta=FakeLetta))

    response = agent_workbench_bridge.dispatch(
        {
            "action": "create_and_run",
            "goal": BLACKBOX_GOAL,
            "run_id": "blackbox-m678-monthly",
            "runtime": "letta",
            "workspace": str(tmp_path),
        }
    )

    assert response["success"] is True
    assert response["runtime"] == "letta"
    assert response["spec"]["workflow"][0]["skill"] == "data_analysis"
    assert response["spec"]["workflow"][0]["input"]["time_grain"] == "monthly"
    assert response["spec"]["workflow"][0]["input"]["requested_periods"] == 3
    exposed_tools = {tool["name"] for tool in fake_messages.calls[0]["client_tools"]}
    assert exposed_tools == {"yield_report_download", "yield_data_analysis"}

    summary = response["data"]["summary"]
    data_analysis_step = next(
        step for step in summary["steps"] if step["step_id"] == "letta_yield_data_analysis"
    )
    assert data_analysis_step["success"] is True

    analysis_artifact = next(
        artifact
        for artifact in summary["artifacts"]
        if artifact["description"] == "data_analysis result text"
    )
    result_text = Path(analysis_artifact["path"]).read_text(encoding="utf-8")

    assert "M678 最近3个月月度良率变化趋势" in result_text
    assert "| M4 | 95.00% |" in result_text
    assert "| M6 | 92.00% |" in result_text
    assert "恶化判断: 末期良率低于首期，存在恶化" in result_text
    assert "恶化原因线索" in result_text
    assert "不良或占比上升" in result_text


def _write_daily_yield_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "屏体综合良率"
    sheet.append(["ProductCode", "指标", "M4", "M5", "M6"])
    sheet.append(["M678", "屏体综合良率", 0.95, 0.94, 0.92])
    sheet.append(["", "综合不良占比", 0.01, 0.02, 0.04])
    workbook.save(path)
