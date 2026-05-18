"""
config.py: ConfigLoader 配置工厂

本模块实现了基于 Pydantic V2 的链式配置加载体系:
    加载顺序: 默认值 → global.yaml → 产品级 YAML → 环境变量 (.env)

核心功能:
1. YAML 文件加载与深度合并 (支持全局配置 + 产品级覆盖)
2. Pydantic V2 严格校验 (类型检查、必填字段验证)
3. 单例模式: 通过模块级实例隐式实现
4. 链式访问: config.paths.base_dir, config.llm.provider

使用方式:
    from yield_report.shared_kernel.config import config
    cfg = config.get()
    print(cfg.paths.base_dir)

    或通过路径加载:
    cfg = config.load("config/global.yaml")

单例实现原理:
    模块级 _instance 缓存 + get() 懒加载。
    首次调用自动从默认路径加载，之后返回缓存实例。
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from yield_report.shared_kernel.config_model import AppConfig


def _deep_merge(base: dict, override: dict) -> dict:
    """递归深度合并两个字典，override 的值会覆盖 base 的同名键。"""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml_file(file_path: Path) -> dict:
    """安全加载单个 YAML 文件，返回字典。"""
    if not file_path.exists():
        return {}
    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _load_env_overrides() -> dict:
    """
    从 .env 加载环境变量，构造用于覆盖配置的嵌套字典。

    环境变量命名规则:
        LLM_PROVIDER        → llm.provider
        LLM_DEEPSEEK_API_KEY → llm.deepseek.api_key
        LOG_LEVEL           → logging.level
        LLM_GEMINI_API_KEY  → llm.gemini.api_key
    """
    load_dotenv()
    overrides: dict = {}

    # LLM 供应商
    if provider := os.getenv("LLM_PROVIDER"):
        overrides.setdefault("llm", {})["provider"] = provider

    # DeepSeek 配置
    if key := os.getenv("DEEPSEEK_API_KEY"):
        overrides.setdefault("llm", {}).setdefault("deepseek", {})["api_key"] = key
    if url := os.getenv("DEEPSEEK_BASE_URL"):
        overrides.setdefault("llm", {}).setdefault("deepseek", {})["base_url"] = url

    # Gemini 配置
    if key := os.getenv("GEMINI_API_KEY"):
        overrides.setdefault("llm", {}).setdefault("gemini", {})["api_key"] = key

    # 日志级别
    if log_level := os.getenv("LOG_LEVEL"):
        overrides.setdefault("logging", {})["level"] = log_level

    # 输出目录
    if output_dir := os.getenv("OUTPUT_DIR"):
        overrides.setdefault("paths", {})["output_dir"] = output_dir

    return overrides


class ConfigLoader:
    """
    配置加载器 (单例)

    调用链:
        1. 从 global.yaml 加载全局配置
        2. 递归加载 config/products/ 下的产品级配置
        3. 深度合并 (产品级覆盖全局)
        4. 从 .env 加载环境变量覆盖
        5. 通过 Pydantic V2 校验并返回 AppConfig 实例
    """

    _instance: ConfigLoader | None = None
    _config: AppConfig | None = None

    def __new__(cls, *args, **kwargs) -> ConfigLoader:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_dir: Path | None = None) -> None:
        """初始化时仅首次有效，后续调用忽略。"""
        # 始终更新 config_dir，以支持测试中的不同临时目录
        if config_dir is not None:
            self._config_dir = config_dir
        elif not hasattr(self, "_config_dir"):
            self._config_dir = Path("config")
        if self._config is not None:
            return
        self._config = None

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    def load(
        self,
        global_yaml: str | Path | None = None,
    ) -> AppConfig:
        """
        执行完整的配置加载链路。

        Args:
            global_yaml: 全局 YAML 文件的路径 (相对于 config_dir 或绝对路径)

        Returns:
            AppConfig: 经过 Pydantic V2 校验的全局配置对象
        """
        # 1. 确定全局配置文件路径
        if global_yaml is None:
            global_yaml = self._config_dir / "global.yaml"
        else:
            global_yaml = Path(global_yaml)
            if not global_yaml.is_absolute():
                global_yaml = self._config_dir / global_yaml

        # 2. 加载全局 YAML
        raw_config: dict = _load_yaml_file(global_yaml)

        # 3. 加载产品级配置并合并
        products_dir = self._config_dir / "products"
        if products_dir.exists():
            for product_file in sorted(products_dir.glob("*.yaml")):
                product_raw = _load_yaml_file(product_file)
                if product_raw:
                    raw_config = _deep_merge(raw_config, product_raw)

        # 4. 加载 .env 环境变量覆盖 (最高优先级)
        env_overrides = _load_env_overrides()
        raw_config = _deep_merge(raw_config, env_overrides)

        # 5. Pydantic V2 严格校验
        self._config = AppConfig.model_validate(raw_config)
        return self._config

    def get(self) -> AppConfig:
        """
        获取当前配置实例。如果尚未加载，则使用默认路径自动加载。

        Returns:
            AppConfig: 全局配置对象
        """
        if self._config is None:
            return self.load()
        return self._config

    def reload(self) -> AppConfig:
        """强制重新加载所有配置（清除缓存）。"""
        self._config = None
        return self.load()


# ======== 模块级单例 ========
config = ConfigLoader()
"""
模块级单例实例。

使用方式:
    from yield_report.shared_kernel.config import config
    cfg = config.get()
    print(cfg.paths.base_dir)
    print(cfg.llm.provider)
"""
