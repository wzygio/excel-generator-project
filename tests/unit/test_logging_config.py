from __future__ import annotations

import logging
from pathlib import Path

from shared_kernel.config_model import AppConfig
from yield_report.agent.spec_model import RunContext
from yield_report.infrastructure.logging_config import (
    configure_yield_report_logging,
    configure_yield_report_logging_for_context,
    reset_yield_report_logging,
    resolve_log_dir,
)


def test_legacy_logs_dir_is_normalized_under_output(tmp_path: Path) -> None:
    cfg = AppConfig(
        paths={
            "base_dir": str(tmp_path),
            "log_dir": "logs",
            "output_dir": "output",
        }
    )

    assert resolve_log_dir(cfg) == tmp_path / "output" / "logs"


def test_configured_log_dir_uses_output_logs(tmp_path: Path) -> None:
    cfg = AppConfig(
        paths={
            "base_dir": str(tmp_path),
            "log_dir": "output/logs",
            "output_dir": "output",
        }
    )

    assert resolve_log_dir(cfg) == tmp_path / "output" / "logs"


def test_configure_logging_creates_managed_hierarchical_handlers(tmp_path: Path) -> None:
    cfg = AppConfig(
        paths={
            "base_dir": str(tmp_path),
            "log_dir": "output/logs",
            "output_dir": "output",
        },
        logging={"level": "INFO", "max_days": 7},
    )
    root_logger = logging.getLogger()

    try:
        all_log_path = configure_yield_report_logging(app_config=cfg, force=True)
        configure_yield_report_logging(app_config=cfg)

        managed_handlers = [
            handler
            for handler in root_logger.handlers
            if getattr(handler, "_yield_report_managed_handler", False)
        ]
        assert len(managed_handlers) == 2
        assert all_log_path == tmp_path / "output" / "logs" / "all.log"

        logger = logging.getLogger("yield_report.skills.daily_report.implementation")
        logger.info(
            "workflow started",
            extra={"event": "start", "purpose": "diagnostic", "run_id": "run-1"},
        )
        logger.error(
            "workflow failed",
            extra={
                "event": "failure",
                "purpose": "business",
                "run_id": "run-1",
                "error_code": "daily_report.analysis.blocked",
            },
        )
        for handler in managed_handlers:
            handler.flush()

        content = all_log_path.read_text(encoding="utf-8")
        assert "yield_report.skills.daily_report.implementation" in content
        assert "event=start" in content
        assert "purpose=diagnostic" in content
        assert "run_id=run-1" in content

        info_content = (
            tmp_path / "output" / "logs" / "skills_daily_report" / "info.log"
        ).read_text(encoding="utf-8")
        error_content = (
            tmp_path / "output" / "logs" / "skills_daily_report" / "error.log"
        ).read_text(encoding="utf-8")
        assert "workflow started" in info_content
        assert "workflow failed" in error_content
        assert "error_code=daily_report.analysis.blocked" in error_content
    finally:
        reset_yield_report_logging()


def test_context_output_dir_controls_log_dir(tmp_path: Path) -> None:
    context = RunContext(run_id="run-1", workspace=tmp_path, output_dir=Path("custom-output"))

    try:
        log_path = configure_yield_report_logging_for_context(context)
        assert log_path == tmp_path / "custom-output" / "logs" / "all.log"
    finally:
        reset_yield_report_logging()
