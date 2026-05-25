"""
conftest.py: Pytest Fixtures

提供测试所需的共享 Fixture，包括:
1. 临时目录与配置文件
2. 预配置的 AppConfig 实例
3. 测试用的 LLM mock
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest
import yaml

from shared_kernel.config import ConfigLoader
from shared_kernel.config_model import AppConfig


@pytest.fixture(autouse=True)
def _reset_config_loader(monkeypatch: pytest.MonkeyPatch):
    """每个测试前阻止 .env 环境变量覆盖，测试后重置 ConfigLoader 单例。"""
    # 阻止 _load_env_overrides 从 .env 加载真实值，确保测试使用临时配置
    monkeypatch.setattr(
        "shared_kernel.config._load_env_overrides",
        lambda: {},
    )
    yield
    ConfigLoader._instance = None
    ConfigLoader._config = None


# ============================================================
# Fixtures: 配置
# ============================================================

@pytest.fixture(scope="session")
def test_resources_dir() -> Path:
    """返回测试资源目录。"""
    return Path(__file__).parent / "resources"


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """创建临时配置目录，包含基础的 global.yaml。"""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    # 写入一个最小的 global.yaml
    minimal_config = {
        "app_name": "TestApp",
        "version": "0.0.1",
        "paths": {
            "base_dir": str(tmp_path),
            "resources_dir": str(tmp_path / "resources"),
            "temp_dir": str(tmp_path / "temp"),
            "log_dir": str(tmp_path / "logs"),
            "output_dir": str(tmp_path / "output"),
        },
        "llm": {
            "provider": "deepseek",
            "deepseek": {
                "api_key": "test-key",
                "base_url": "https://api.deepseek.com",
            },
        },
    }

    with open(config_dir / "global.yaml", "w", encoding="utf-8") as f:
        yaml.dump(minimal_config, f)

    yield config_dir


@pytest.fixture
def test_app_config(temp_config_dir: Path) -> AppConfig:
    """返回从临时配置加载的 AppConfig 实例。"""
    loader = ConfigLoader(config_dir=temp_config_dir)
    return loader.load()


# ============================================================
# Fixtures: LLM Mock
# ============================================================

@pytest.fixture
def mock_llm_response() -> str:
    """模拟 LLM 返回的 Gap 分析结果。"""
    return """
    【当日Gap解释】
    产品A的 Group1 Gap 最大，为 0.85%，主要因 CodeA 不良率上升导致。
    批次分析：最新批次 B20260301 产出率 35%，不良率 2.1% 高于前三批次最大值 1.5%，判定为批次恶化。
    影响最大的 Code 为 CodeA（贡献 0.5%）。
    """


@pytest.fixture
def mock_exception_analysis_response() -> str:
    """模拟 LLM 返回的异常分析结果。"""
    return """
    【当日异常】
    新增异常：<span style="color:red">CodeX 不良率 0.3%</span>（CT站点）
    影响当日良率的已知异常：<span style="color:orange">CodeY 不良率 0.2%</span>（Array站点）
    """


@pytest.fixture
def mock_trend_analysis_response() -> str:
    """模拟 LLM 返回的趋势分析结果。"""
    return """
    【趋势分析】
    产品A 良率连续 3 日下降（87.2% → 86.5% → 85.8%），需重点关注。
    """
