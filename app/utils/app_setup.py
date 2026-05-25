"""
app_setup.py: 应用初始化

负责:
1. 加载 .env 环境变量 (dotenv)
2. 初始化日志系统 (setup_logging)
3. 初始化配置工厂 (ConfigLoader)
4. 提供便捷的环境检查工具

使用方式:
    from app.utils.app_setup import initialize_app

    if __name__ == "__main__":
        config = initialize_app()
        print(f"配置加载完成: {config.app_name} v{config.version}")
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from app.utils.logger_setup import setup_logging
from shared_kernel.config import config as config_loader
from shared_kernel.config_model import AppConfig


def load_environment(env_path: Optional[str | Path] = None) -> None:
    """
    加载 .env 环境变量文件。

    Args:
        env_path: .env 文件路径，默认为项目根目录的 .env
    """
    if env_path is None:
        # 自动向上查找 .env 文件
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            candidate = parent / ".env"
            if candidate.exists():
                env_path = candidate
                break

    if env_path and Path(env_path).exists():
        load_dotenv(dotenv_path=str(env_path), override=True)
        print(f"[AppSetup] .env 文件已加载: {env_path}")
    else:
        print(
            "[AppSetup] 未找到 .env 文件，将使用默认配置。"
            "如需配置 API Key，请复制 .env.example 为 .env 并填写。"
        )


def initialize_app(
    env_path: Optional[str | Path] = None,
    config_dir: Optional[str | Path] = None,
    log_dir: str | Path = "logs",
    log_level: Optional[str] = None,
) -> AppConfig:
    """
    完整初始化应用环境。

    调用链:
        加载 .env → 初始化日志 → 加载配置 → 返回 AppConfig

    Args:
        env_path: .env 文件路径
        config_dir: 配置目录路径 (包含 global.yaml)
        log_dir: 日志目录
        log_level: 日志级别 (覆盖 .env 中的配置)

    Returns:
        AppConfig: 初始化后的全局配置对象
    """
    # 1. 加载 .env (必须在其他操作之前，因为日志和配置可能依赖环境变量)
    load_environment(env_path)

    # 2. 确定日志级别
    effective_log_level = (
        log_level or os.getenv("LOG_LEVEL", "INFO")
    )

    # 3. 初始化日志系统
    setup_logging(log_dir=log_dir, level=effective_log_level)

    # 4. 加载配置
    if config_dir:
        config_loader._config_dir = Path(config_dir)

    app_config = config_loader.load()
    
    import logging
    logging.info("应用初始化完成: %s v%s", app_config.app_name, app_config.version)
    logging.info("LLM 供应商: %s", app_config.llm.provider)

    return app_config


def check_environment() -> dict[str, bool]:
    """
    检查运行环境的健康状态。

    Returns:
        dict 包含各项检查结果:
        {
            "dotenv_loaded": True/False,
            "deepseek_key_set": True/False,
            "gemini_key_set": True/False,
            "config_file_exists": True/False,
            "logs_writable": True/False,
        }
    """
    checks = {}

    # .env 是否已加载
    checks["dotenv_loaded"] = os.getenv("DEEPSEEK_API_KEY") is not None or os.getenv("GEMINI_API_KEY") is not None

    # API Key 是否已设置
    checks["deepseek_key_set"] = bool(os.getenv("DEEPSEEK_API_KEY"))
    checks["gemini_key_set"] = bool(os.getenv("GEMINI_API_KEY"))

    # 配置文件是否存在
    checks["config_file_exists"] = Path("config/global.yaml").exists()

    # 日志目录是否可写
    try:
        Path("logs").mkdir(parents=True, exist_ok=True)
        checks["logs_writable"] = True
    except PermissionError:
        checks["logs_writable"] = False

    return checks


def print_startup_banner(config: AppConfig) -> None:
    """打印启动 Banner。"""
    banner = f"""
{'=' * 60}
  {config.app_name} v{config.version}
  良率日报自动生成系统
{'=' * 60}
  LLM 供应商: {config.llm.provider}
  日志目录:   logs/
  配置目录:   config/
{'=' * 60}
"""
    print(banner)
