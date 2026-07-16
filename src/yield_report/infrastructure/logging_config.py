"""Central logging configuration for yield_report workflows."""

from __future__ import annotations

import logging
import re
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from yield_report.shared_kernel.config import ConfigLoader
from yield_report.shared_kernel.config_model import AppConfig

DEFAULT_LOG_FILENAME = "all.log"
DEFAULT_LOG_DIR = Path("output") / "logs"
MANAGED_HANDLER_ATTR = "_yield_report_managed_handler"
MANAGED_HANDLER_BASE_DIR_ATTR = "_yield_report_log_base_dir"
MANAGED_HANDLER_PATH_ATTR = "_yield_report_log_path"
logger = logging.getLogger(__name__)


class YieldReportFormatter(logging.Formatter):
    """Formatter that keeps structured logging fields optional."""

    DEFAULT_FIELDS = {
        "event": "-",
        "purpose": "-",
        "run_id": "-",
        "task_id": "-",
        "error_code": "-",
        "output_path": "-",
    }

    def format(self, record: logging.LogRecord) -> str:
        for field_name, default_value in self.DEFAULT_FIELDS.items():
            if not hasattr(record, field_name):
                setattr(record, field_name, default_value)
        return super().format(record)


class ModuleLevelFileHandler(logging.Handler):
    """Route records to output/logs/<functional-module>/<level>.log."""

    def __init__(
        self,
        *,
        base_dir: Path,
        when: str,
        backup_count: int,
        formatter: logging.Formatter,
    ) -> None:
        super().__init__(logging.NOTSET)
        self.base_dir = base_dir
        self.when = when
        self.backup_count = backup_count
        self.formatter = formatter
        self._handlers: dict[tuple[str, str], TimedRotatingFileHandler] = {}

    def emit(self, record: logging.LogRecord) -> None:
        try:
            module = _functional_module_from_logger(record.name)
            level = record.levelname.lower()
            handler = self._get_handler(module, level)
            handler.emit(record)
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        for handler in self._handlers.values():
            handler.flush()

    def close(self) -> None:
        for handler in self._handlers.values():
            handler.close()
        self._handlers.clear()
        super().close()

    def _get_handler(self, module: str, level: str) -> TimedRotatingFileHandler:
        key = (module, level)
        if key not in self._handlers:
            path = self.base_dir / module / f"{level}.log"
            self._handlers[key] = _build_timed_handler(
                log_path=path,
                level=logging.NOTSET,
                when=self.when,
                backup_count=self.backup_count,
                formatter=self.formatter,
            )
        return self._handlers[key]


def configure_yield_report_logging(
    *,
    app_config: AppConfig | None = None,
    log_dir: str | Path | None = None,
    level: str | int | None = None,
    force: bool = False,
) -> Path:
    """Configure the project logger and return the complete-chain log path."""

    config = app_config or _load_app_config()
    resolved_level = _normalize_level(level or config.logging.level)
    resolved_dir = resolve_log_dir(config, log_dir=log_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)
    all_log_path = resolved_dir / DEFAULT_LOG_FILENAME

    root_logger = logging.getLogger()
    managed_handlers = _managed_handlers(root_logger)
    same_base_dir = (
        managed_handlers
        and all(
            getattr(handler, MANAGED_HANDLER_BASE_DIR_ATTR, None) == resolved_dir
            for handler in managed_handlers
        )
    )

    if force or (managed_handlers and not same_base_dir):
        _remove_managed_handlers(root_logger)
        managed_handlers = []
        same_base_dir = False

    if not managed_handlers or not same_base_dir:
        formatter = _build_formatter()
        all_handler = _build_timed_handler(
            log_path=all_log_path,
            level=resolved_level,
            when=config.logging.domain_rotation,
            backup_count=config.logging.max_days,
            formatter=formatter,
        )
        router_handler = ModuleLevelFileHandler(
            base_dir=resolved_dir,
            when=_normalize_rotation(config.logging.domain_rotation),
            backup_count=config.logging.max_days,
            formatter=formatter,
        )
        router_handler.setLevel(resolved_level)

        for handler in (all_handler, router_handler):
            setattr(handler, MANAGED_HANDLER_ATTR, True)
            setattr(handler, MANAGED_HANDLER_BASE_DIR_ATTR, resolved_dir)
            root_logger.addHandler(handler)
    else:
        for handler in managed_handlers:
            handler.setLevel(resolved_level)

    if root_logger.level == logging.NOTSET or root_logger.level > resolved_level:
        root_logger.setLevel(resolved_level)
    logging.getLogger("yield_report").setLevel(resolved_level)
    return all_log_path


def configure_yield_report_logging_for_context(context: Any | None) -> Path:
    """Configure logging under a RunContext output directory when available."""

    if context is None:
        return configure_yield_report_logging()

    workspace = Path(getattr(context, "workspace", Path.cwd()))
    output_dir = Path(getattr(context, "output_dir", DEFAULT_LOG_DIR.parent))
    if not output_dir.is_absolute():
        output_dir = workspace / output_dir
    return configure_yield_report_logging(log_dir=output_dir / "logs")


def resolve_log_dir(
    app_config: AppConfig | None = None,
    *,
    log_dir: str | Path | None = None,
) -> Path:
    """Resolve the canonical log directory.

    Historical configs may still say ``logs``. Normalize that old default to
    ``output/logs`` so generated logs stay under the project output tree.
    """

    config = app_config or _load_app_config()
    configured = Path(log_dir) if log_dir is not None else Path(config.paths.log_dir)

    if configured == Path("logs"):
        configured = Path(config.paths.output_dir) / "logs"

    if configured.is_absolute():
        return configured

    base_dir = Path(config.paths.base_dir)
    if base_dir == Path("."):
        return configured
    return base_dir / configured


def reset_yield_report_logging() -> None:
    """Remove handlers installed by this module. Intended for tests."""

    _remove_managed_handlers(logging.getLogger())


def _load_app_config() -> AppConfig:
    try:
        return ConfigLoader().get()
    except Exception:
        logger.debug("Falling back to default logging config", exc_info=True)
        return AppConfig()


def _build_formatter() -> YieldReportFormatter:
    return YieldReportFormatter(
        "%(asctime)s %(levelname)s %(name)s "
        "event=%(event)s purpose=%(purpose)s run_id=%(run_id)s task_id=%(task_id)s "
        "error_code=%(error_code)s output_path=%(output_path)s %(message)s"
    )


def _build_timed_handler(
    *,
    log_path: Path,
    level: int,
    when: str,
    backup_count: int,
    formatter: logging.Formatter,
) -> TimedRotatingFileHandler:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        log_path,
        when=_normalize_rotation(when),
        backupCount=max(0, backup_count),
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    setattr(handler, MANAGED_HANDLER_PATH_ATTR, log_path)
    return handler


def _managed_handlers(logger: logging.Logger) -> list[logging.Handler]:
    return [
        handler
        for handler in logger.handlers
        if getattr(handler, MANAGED_HANDLER_ATTR, False)
    ]


def _remove_managed_handlers(logger: logging.Logger) -> None:
    for handler in _managed_handlers(logger):
        logger.removeHandler(handler)
        handler.close()


def _normalize_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    value = logging.getLevelName(str(level).upper())
    return value if isinstance(value, int) else logging.INFO


def _normalize_rotation(rotation: str) -> str:
    value = str(rotation or "midnight").lower()
    if value in {"midnight", "s", "m", "h", "d", "w0", "w1", "w2", "w3", "w4", "w5", "w6"}:
        return value
    return "midnight"


def _functional_module_from_logger(logger_name: str) -> str:
    parts = logger_name.split(".")
    if parts[:1] != ["yield_report"]:
        return "external"
    if len(parts) >= 3 and parts[1] == "skills":
        return _safe_path_part(f"skills_{parts[2]}")
    if len(parts) >= 2:
        return _safe_path_part(parts[1])
    return "root"


def _safe_path_part(value: str) -> str:
    safe_value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe_value.strip("._-") or "unknown"
