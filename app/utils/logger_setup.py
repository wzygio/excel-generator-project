"""
logger_setup.py: [企业级日志架构] 按领域+级别二维隔离

本模块实现了对 Python logging 模块的高级封装，采用"用途 × 领域"二维隔离策略:

领域分流（纵轴）:
    根据代码文件路径自动将日志分流到对应领域的 .log 文件。
    例如 src/yield_report/core/gap_analysis.py 的日志会写入 logs/core.log。
    而 app/main.py 的日志会写入 logs/app.log。

级别隔离（横轴）:
    每个领域下区分:
    - 全量流水 (ALL): 完整的 INFO 及以上日志，写入 {domain}.log
    - 高优报警 (ERROR): 仅 ERROR 及以上日志，写入 {domain}.error.log
    - 独立调试追踪 (TRACE): DEBUG 级别日志，写入 {domain}.trace.log

轮转策略:
    按天午夜零点自动轮转 (when="midnight")，保留最近 30 天日志，过期自动清理。

使用方式:
    # 在各模块顶部直接使用标准 logging 即可:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("这是一条 INFO 日志")
    logger.error("这是一条 ERROR 日志")

    # 日志会自动路由到对应的领域日志文件。
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional


_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _resolve_domain_name(logger_name: str) -> str:
    """
    根据 logger 名称解析领域名称。

    规则:
        yield_report.shared_kernel.config → shared_kernel
        yield_report.yield_report.core.gap → yield_report.core
        app.main → app
        __main__ → root
    """
    parts = logger_name.split(".")
    if len(parts) >= 3 and parts[0] == "yield_report":
        # src/yield_report/shared_kernel/... → shared_kernel
        # src/yield_report/yield_report/core/... → yield_report.core
        return ".".join(parts[1:-1]) if len(parts) > 2 else parts[1]
    elif len(parts) >= 1 and parts[0] == "app":
        return "app"
    return "root"


class DomainLogger:
    """
    领域日志管理器。

    每个 logger 名称自动映射到一个领域，并为该领域创建三个文件句柄:
    - {domain}.log:      INFO 及以上级别 (全量流水)
    - {domain}.error.log: ERROR 及以上级别 (高优报警)
    - {domain}.trace.log: DEBUG 级别 (调试追踪)
    """

    _initialized: bool = False
    _log_dir: Path = Path("logs")

    @classmethod
    def initialize(
        cls,
        log_dir: str | Path = "logs",
        default_level: str = "INFO",
        max_days: int = 30,
    ) -> None:
        """
        初始化日志系统。全局仅需调用一次。

        Args:
            log_dir: 日志文件存储目录
            default_level: 默认日志级别 (DEBUG/INFO/WARNING/ERROR)
            max_days: 日志文件保留天数
        """
        if cls._initialized:
            return

        cls._log_dir = Path(log_dir)
        cls._log_dir.mkdir(parents=True, exist_ok=True)
        cls._max_days = max_days
        cls._default_level = getattr(logging, default_level.upper(), logging.INFO)

        # 安装自定义的 Logger 工厂
        logging.setLoggerClass(_DomainAwareLogger)

        # 设置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # 由各 handler 控制级别

        # 添加控制台 Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(cls._default_level)
        console_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
        root_logger.addHandler(console_handler)

        cls._initialized = True
        logging.info(
            "日志系统初始化完成 | 目录=%s | 级别=%s | 保留=%d天",
            log_dir,
            default_level,
            max_days,
        )

    @classmethod
    def get_domain_file_handlers(
        cls, domain: str
    ) -> list[logging.Handler]:
        """
        为指定领域创建三个文件 Handler。

        Returns:
            [info_handler, error_handler, trace_handler]
        """
        handlers = []

        # 1. 全量流水: {domain}.log (INFO 及以上)
        info_path = cls._log_dir / f"{domain}.log"
        info_handler = logging.handlers.TimedRotatingFileHandler(
            filename=info_path,
            when="midnight",
            interval=1,
            backupCount=cls._max_days,
            encoding="utf-8",
        )
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
        handlers.append(info_handler)

        # 2. 高优报警: {domain}.error.log (ERROR 及以上)
        error_path = cls._log_dir / f"{domain}.error.log"
        error_handler = logging.handlers.TimedRotatingFileHandler(
            filename=error_path,
            when="midnight",
            interval=1,
            backupCount=cls._max_days,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
        handlers.append(error_handler)

        # 3. 调试追踪: {domain}.trace.log (DEBUG 级别)
        trace_path = cls._log_dir / f"{domain}.trace.log"
        trace_handler = logging.handlers.TimedRotatingFileHandler(
            filename=trace_path,
            when="midnight",
            interval=1,
            backupCount=cls._max_days,
            encoding="utf-8",
        )
        trace_handler.setLevel(logging.DEBUG)
        trace_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
        handlers.append(trace_handler)

        return handlers


class _DomainAwareLogger(logging.Logger):
    """
    自定义 Logger 类，在创建时自动添加领域文件 Handler。

    通过 logging.setLoggerClass(_DomainAwareLogger) 安装后，
    所有 logging.getLogger(name) 调用都会返回此类的实例。
    """

    def __init__(self, name: str, level=logging.NOTSET):
        super().__init__(name, level)
        if not DomainLogger._initialized:
            return

        # 跳过根日志器
        if name in ("root", "") or name.startswith("uvicorn") or name.startswith("streamlit"):
            return

        domain = _resolve_domain_name(name)
        # 避免重复添加
        if not any(
            isinstance(h, logging.handlers.TimedRotatingFileHandler)
            and domain in str(getattr(h, "baseFilename", ""))
            for h in self.handlers
        ):
            for handler in DomainLogger.get_domain_file_handlers(domain):
                self.addHandler(handler)


def setup_logging(
    log_dir: str | Path = "logs",
    level: str = "INFO",
    max_days: int = 30,
) -> None:
    """
    便捷入口: 一键配置完整日志系统。

    这是 app_setup.py 和其他模块初始化日志的标准入口。

    Args:
        log_dir: 日志目录
        level: 日志级别
        max_days: 保留天数
    """
    DomainLogger.initialize(
        log_dir=log_dir,
        default_level=level,
        max_days=max_days,
    )
    logging.info("=" * 60)
    logging.info("日志系统启动 | 级别=%s | 目录=%s", level, log_dir)
    logging.info("=" * 60)
