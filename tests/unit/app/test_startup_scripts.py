from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_start_daily_report_ui_script_runs_streamlit_entrypoint() -> None:
    content = (REPO_ROOT / "start_daily_report_ui.bat").read_text(encoding="utf-8")

    assert "app\\daily_report_app.py" in content
    assert "--server.port %PORT%" in content
    assert "set \"PORT=8502\"" in content
    assert "set \"PYTHONPATH=%cd%\\src;%cd%;%PYTHONPATH%\"" in content
    assert "taskkill /PID" in content


def test_hidden_runner_points_to_daily_report_ui_script() -> None:
    content = (REPO_ROOT / "run_hidden.vbs").read_text(encoding="utf-8")

    assert "start_daily_report_ui.bat" in content
    assert ", 0, False" in content
