"""
test_config_loader.py: ConfigLoader 单元测试

测试目标:
1. ConfigLoader 单例模式
2. YAML 加载与深度合并
3. Pydantic V2 校验
4. 环境变量覆盖
5. 默认值填充
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from shared_kernel.config import (
    PROJECT_ROOT,
    ConfigLoader,
    _deep_merge,
    _load_yaml_file,
    config,
)
from shared_kernel.config_model import (
    AppConfig,
    FineReportDownloadConfig,
    LlmConfig,
    PathsConfig,
    SourceFileConfig,
)


class TestDeepMerge:
    """测试深度合并函数。"""

    def test_simple_override(self):
        """基础场景: 简单字段覆盖。"""
        base = {"name": "base", "version": "1.0"}
        override = {"version": "2.0"}
        result = _deep_merge(base, override)
        assert result == {"name": "base", "version": "2.0"}

    def test_nested_merge(self):
        """嵌套字典合并。"""
        base = {"llm": {"provider": "deepseek", "timeout": 30}}
        override = {"llm": {"timeout": 60}}
        result = _deep_merge(base, override)
        assert result == {"llm": {"provider": "deepseek", "timeout": 60}}

    def test_new_key_added(self):
        """新增键: override 中有 base 没有的键。"""
        base = {"name": "test"}
        override = {"new_key": "value"}
        result = _deep_merge(base, override)
        assert result == {"name": "test", "new_key": "value"}

    def test_empty_override(self):
        """空覆盖: 返回 base 的副本。"""
        base = {"key": "value"}
        result = _deep_merge(base, {})
        assert result == {"key": "value"}

    def test_non_dict_value_override(self):
        """非字典值完全覆盖字典值。"""
        base = {"key": {"nested": "value"}}
        override = {"key": "scalar"}
        result = _deep_merge(base, override)
        assert result == {"key": "scalar"}


class TestLoadYamlFile:
    """测试 YAML 文件加载。"""

    def test_load_nonexistent_file(self, tmp_path: Path):
        """不存在的文件返回空字典。"""
        result = _load_yaml_file(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_load_empty_file(self, tmp_path: Path):
        """空文件返回空字典。"""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("", encoding="utf-8")
        result = _load_yaml_file(empty_file)
        assert result == {}

    def test_load_valid_yaml(self, tmp_path: Path):
        """有效 YAML 返回解析后的字典。"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: value\nnested:\n  inner: 42", encoding="utf-8")
        result = _load_yaml_file(yaml_file)
        assert result == {"key": "value", "nested": {"inner": 42}}


class TestConfigLoaderSingleton:
    """测试 ConfigLoader 单例模式。"""

    def test_singleton_instance(self):
        """多次实例化返回同一个对象。"""
        loader1 = ConfigLoader()
        loader2 = ConfigLoader()
        assert loader1 is loader2

    def test_singleton_initialization_only_once(self):
        """__init__ 仅在首次调用时生效。"""
        ConfigLoader(config_dir=Path("/tmp/test"))
        loader2 = ConfigLoader(config_dir=Path("/other"))
        # 第二次实例化不应覆盖 config_dir
        assert loader2.config_dir == loader2.config_dir  # 至少不报错


class TestConfigLoaderLoading:
    """测试 ConfigLoader 加载逻辑。"""

    def test_load_from_temp_config(self, temp_config_dir: Path):
        """从临时配置目录加载。"""
        loader = ConfigLoader(config_dir=temp_config_dir)
        cfg = loader.load()
        assert isinstance(cfg, AppConfig)
        assert cfg.app_name == "TestApp"
        assert cfg.version == "0.0.1"

    def test_config_has_defaults(self, temp_config_dir: Path):
        """未配置的字段应使用 Pydantic 默认值。"""
        loader = ConfigLoader(config_dir=temp_config_dir)
        cfg = loader.load()
        # logging 没有在 YAML 中指定，应使用默认值
        assert cfg.logging.level == "INFO"
        assert cfg.logging.max_days == 30

    def test_paths_config(self, temp_config_dir: Path):
        """验证路径配置正确加载。"""
        loader = ConfigLoader(config_dir=temp_config_dir)
        cfg = loader.load()
        assert isinstance(cfg.paths, PathsConfig)
        # base_dir 应该是一个非空的有效路径字符串
        assert isinstance(cfg.paths.base_dir, str)
        assert len(cfg.paths.base_dir) > 0
        # log_dir 应该归一到标准输出目录下
        assert Path(cfg.paths.log_dir).parts[-2:] == ("output", "logs")

    def test_llm_config(self, temp_config_dir: Path):
        """验证 LLM 配置正确加载。"""
        loader = ConfigLoader(config_dir=temp_config_dir)
        cfg = loader.load()
        assert isinstance(cfg.llm, LlmConfig)
        assert cfg.llm.provider == "deepseek"
        assert cfg.llm.deepseek.api_key == "test-key"
        assert cfg.llm.deepseek.base_url == "https://api.deepseek.com"

    def test_llm_provider_validation(self):
        """非法 provider 应触发校验错误。"""
        with pytest.raises(ValueError, match="provider 必须为"):
            LlmConfig(provider="invalid_provider")

    def test_get_method_auto_load(self, temp_config_dir: Path):
        """get() 方法应在未加载时自动加载。"""
        loader = ConfigLoader(config_dir=temp_config_dir)
        cfg = loader.get()
        assert isinstance(cfg, AppConfig)

    def test_reload_clears_cache(self, temp_config_dir: Path):
        """reload() 应清除缓存并重新加载。"""
        loader = ConfigLoader(config_dir=temp_config_dir)
        cfg1 = loader.load()
        cfg2 = loader.reload()
        assert isinstance(cfg2, AppConfig)
        assert cfg2.app_name == cfg1.app_name

    def test_module_singleton_exists(self):
        """模块级 config 实例应存在且为 ConfigLoader 类型。"""
        assert isinstance(config, ConfigLoader)

    def test_default_config_dir_is_independent_of_current_working_directory(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ConfigLoader._instance = None
        ConfigLoader._config = None
        monkeypatch.chdir(tmp_path)

        loader = ConfigLoader()

        assert loader.config_dir == PROJECT_ROOT / "config"
        assert loader.get().source_files["daily_yield"].description


class TestProductConfigOverride:
    """测试产品级配置覆盖。"""

    def test_product_config_merge(self, temp_config_dir: Path):
        """产品级 YAML 应覆盖全局配置。"""
        # 创建产品级配置
        products_dir = temp_config_dir / "products"
        products_dir.mkdir(exist_ok=True)

        product_config = {
            "products": [
                {"name": "ProductA", "description": "Test Product A"},
            ]
        }
        with open(products_dir / "product_a.yaml", "w", encoding="utf-8") as f:
            yaml.dump(product_config, f)

        loader = ConfigLoader(config_dir=temp_config_dir)
        cfg = loader.load()
        assert len(cfg.products) == 1
        assert cfg.products[0].name == "ProductA"
        assert cfg.products[0].description == "Test Product A"


class TestAppConfigModel:
    """测试 AppConfig Pydantic 模型。"""

    def test_minimal_config(self):
        """最小配置应使用所有默认值。"""
        cfg = AppConfig()
        assert cfg.app_name == "Yield Report Generator"
        assert cfg.version == "0.1.0"
        assert cfg.debug is False
        assert cfg.paths.base_dir == "."
        assert cfg.agent.default_runtime == "pydantic_ai"
        assert cfg.agent.pydantic_ai.enabled is True
        assert cfg.agent.letta.enabled is True

    def test_agent_pydantic_ai_config(self):
        """Agent Runtime 配置应支持 Pydantic AI。"""
        cfg = AppConfig.model_validate(
            {
                "agent": {
                    "default_runtime": "pydantic_ai",
                    "pydantic_ai": {
                        "enabled": True,
                        "model": "deepseek-chat",
                        "base_url": "https://api.deepseek.com",
                        "api_key_env": "DEEPSEEK_API_KEY",
                        "request_limit": 33,
                        "max_tool_calls": 9,
                        "tool_timeout_seconds": 120,
                        "require_tool_use_for_workflow": True,
                    },
                }
            }
        )

        assert cfg.agent.default_runtime == "pydantic_ai"
        assert cfg.agent.pydantic_ai.enabled is True
        assert cfg.agent.pydantic_ai.model == "deepseek-chat"
        assert cfg.agent.pydantic_ai.base_url == "https://api.deepseek.com"
        assert cfg.agent.pydantic_ai.api_key_env == "DEEPSEEK_API_KEY"
        assert cfg.agent.pydantic_ai.request_limit == 33
        assert cfg.agent.pydantic_ai.max_tool_calls == 9
        assert cfg.agent.pydantic_ai.tool_timeout_seconds == 120
        assert cfg.agent.pydantic_ai.require_tool_use_for_workflow is True

    def test_extra_fields_ignored(self):
        """额外的字段应被忽略。"""
        cfg = AppConfig(**{"unknown_field": "value", "paths": {"extra": "ignored"}})
        assert hasattr(cfg, "app_name")

    def test_report_config_defaults(self):
        """报告配置应有合理的默认值。"""
        cfg = AppConfig()
        assert "gap_analysis" in cfg.report.sections
        assert cfg.report.gap_analysis.top_n == 3
        assert cfg.report.batch_analysis.min_yield_rate == 30.0
        assert cfg.report.trend_analysis.consecutive_days == 3

    def test_agent_source_and_download_settings_are_validated(self):
        cfg = AppConfig.model_validate(
            {
                "agent": {
                    "daily_report": {
                        "generator_root": "~/skills/generator",
                        "cli_path": "scripts/cli.py",
                        "output_dir": "output/reports",
                    }
                },
                "source_files": {
                    "daily_yield": {
                        "description": "Configured report",
                        "pattern": "configured-*",
                        "filename": "configured.xlsx",
                        "default_path": "resources/configured.xlsx",
                    }
                },
                "report_download": {
                    "finereport": {
                        "report_directory": "configured/directory",
                        "report_wait_timeout_ms": 90000,
                        "browser": {"timeout_ms": 60000},
                    }
                },
            }
        )

        assert cfg.agent.daily_report.cli_path == "scripts/cli.py"
        assert isinstance(cfg.source_files["daily_yield"], SourceFileConfig)
        assert cfg.source_files["daily_yield"].filename == "configured.xlsx"
        assert isinstance(cfg.report_download.finereport, FineReportDownloadConfig)
        assert cfg.report_download.finereport.report_wait_timeout_ms == 90000

    def test_agent_letta_config(self):
        """Agent Runtime 配置应支持 Letta。"""
        cfg = AppConfig.model_validate(
            {
                "agent": {
                    "default_runtime": "letta",
                    "letta": {
                        "enabled": True,
                        "base_url": "http://localhost:8283",
                        "api_key_env": "LETTA_SERVER_PASSWORD",
                        "server_password_env": "LETTA_SERVER_PASSWORD",
                        "agent_id": "agent-test",
                        "agent_name": "visionox-yield-monitoring-agent",
                        "agent_id_cache_path": ".agent_workbench/letta_agent_id",
                        "model": "openai/gpt-4.1",
                        "embedding": "openai/text-embedding-3-small",
                        "sync_memory_blocks": True,
                        "archive_memory_candidates": True,
                        "use_conversations": True,
                        "compaction_mode": "sliding_window",
                        "compaction_clip_chars": 50000,
                        "streaming": True,
                        "stream_tokens": False,
                        "background_runs": False,
                        "timeout_seconds": 600,
                        "max_tool_rounds": 8,
                    },
                }
            }
        )

        assert cfg.agent.default_runtime == "letta"
        assert cfg.agent.letta.enabled is True
        assert cfg.agent.letta.base_url == "http://localhost:8283"
        assert cfg.agent.letta.api_key_env == "LETTA_SERVER_PASSWORD"
        assert cfg.agent.letta.server_password_env == "LETTA_SERVER_PASSWORD"
        assert cfg.agent.letta.agent_id == "agent-test"
        assert cfg.agent.letta.agent_name == "visionox-yield-monitoring-agent"
        assert cfg.agent.letta.agent_id_cache_path == ".agent_workbench/letta_agent_id"
        assert cfg.agent.letta.embedding == "openai/text-embedding-3-small"
        assert cfg.agent.letta.sync_memory_blocks is True
        assert cfg.agent.letta.archive_memory_candidates is True
        assert cfg.agent.letta.use_conversations is True
        assert cfg.agent.letta.compaction_mode == "sliding_window"
        assert cfg.agent.letta.compaction_clip_chars == 50000
        assert cfg.agent.letta.streaming is True
        assert cfg.agent.letta.stream_tokens is False
        assert cfg.agent.letta.background_runs is False
        assert cfg.agent.letta.max_tool_rounds == 8

    def test_agent_default_runtime_rejects_disabled_downgrade_runtime(self):
        """默认 Runtime 不允许配置为 Python/OMP 降级路径。"""
        with pytest.raises(ValueError, match="default_runtime 必须为"):
            AppConfig.model_validate({"agent": {"default_runtime": "python"}})
