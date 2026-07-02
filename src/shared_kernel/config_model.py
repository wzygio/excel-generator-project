"""
config_model.py: Pydantic V2 配置模型定义

本模块定义了完整的 Pydantic V2 配置模型体系，用于:
1. 强类型校验 YAML 配置文件的结构
2. 支持链式访问 (如 config.paths.base_dir)
3. 支持环境变量覆盖 (通过 .env 文件)
4. 提供合理的默认值与详细的校验错误信息

使用方式:
    from shared_kernel.config_model import AppConfig, LlmConfig
    cfg = AppConfig(...)  # 或通过 ConfigLoader 加载

架构:
    AppConfig (根模型)
    ├── paths: PathsConfig        # 路径相关配置
    ├── llm: LlmConfig            # 大模型 API 配置
    ├── logging: LoggingConfig    # 日志配置
    ├── report: ReportConfig      # 报告生成配置
    └── products: list[ProductConfig]  # 产品级配置
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PathsConfig(BaseModel):
    """路径配置模型"""

    base_dir: str = Field(default=".", description="项目根目录")
    resources_dir: str = Field(default="resources", description="资源文件目录")
    temp_dir: str = Field(default="data/temp", description="临时文件目录")
    log_dir: str = Field(default="output/logs", description="日志文件目录")
    output_dir: str = Field(default="output", description="输出文件目录")
    template_file: str = Field(default="template.xlsx", description="模板文件名称")
    temp_file: str = Field(default="temp_output.xlsx", description="临时输出文件")
    output_file: str = Field(default="final_output.xlsx", description="最终输出文件")


class LlmProviderConfig(BaseModel):
    """大模型供应商配置"""

    api_key: str = Field(default="", description="API 密钥")
    base_url: str = Field(default="", description="API 基础 URL")
    model_name: str = Field(default="", description="模型名称")
    timeout: int = Field(default=60, description="请求超时秒数")
    max_retries: int = Field(default=3, description="最大重试次数")


class LlmConfig(BaseModel):
    """大模型全局配置"""

    provider: str = Field(default="deepseek", description="默认供应商: deepseek / gemini")
    deepseek: LlmProviderConfig = Field(
        default_factory=lambda: LlmProviderConfig(
            base_url="https://api.deepseek.com",
            model_name="deepseek-chat",
        )
    )
    gemini: LlmProviderConfig = Field(
        default_factory=lambda: LlmProviderConfig(
            model_name="gemini-2.0-flash",
        )
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"deepseek", "gemini"}
        if v.lower() not in allowed:
            raise ValueError(f"provider 必须为 {allowed} 之一，当前值: {v}")
        return v.lower()


class LoggingConfig(BaseModel):
    """日志配置模型"""

    level: str = Field(default="INFO", description="日志级别")
    domain_rotation: str = Field(default="midnight", description="日志轮转时间")
    max_days: int = Field(default=30, description="日志保留天数")


class ProductConfig(BaseModel):
    """产品级配置"""

    name: str = Field(..., description="产品名称/型号")
    description: str = Field(default="", description="产品描述")
    llm_prompt_overrides: dict[str, str] | None = Field(
        default=None,
        description="针对该产品的 LLM Prompt 覆盖",
    )
    rules: dict | None = Field(default=None, description="产品特定的业务规则")


class GapAnalysisConfig(BaseModel):
    """Gap 分析配置"""

    top_n: int = Field(default=3, description="Top N Gap 数量")
    target_field: str = Field(default="target_defect_rate", description="目标不良率字段名")
    actual_field: str = Field(default="actual_defect_rate", description="实际不良率字段名")
    group_field: str = Field(default="group_name", description="分组字段名")


class BatchAnalysisConfig(BaseModel):
    """批次分析配置"""

    min_yield_rate: float = Field(default=30.0, description="最低产出率百分比阈值")
    comparison_batches: int = Field(default=3, description="对比的历史批次数量")


class TrendAnalysisConfig(BaseModel):
    """趋势分析配置"""

    consecutive_days: int = Field(default=3, description="连续天数")
    consecutive_weeks: int = Field(default=3, description="连续周数")


class ReportConfig(BaseModel):
    """报告生成配置"""

    sections: list[str] = Field(
        default=["gap_analysis", "daily_exception", "known_exception"],
        description="需要生成的报告模块列表",
    )
    gap_analysis: GapAnalysisConfig = Field(default_factory=GapAnalysisConfig)
    batch_analysis: BatchAnalysisConfig = Field(default_factory=BatchAnalysisConfig)
    trend_analysis: TrendAnalysisConfig = Field(default_factory=TrendAnalysisConfig)


class LettaAgentRuntimeConfig(BaseModel):
    """Letta Agent Runtime 配置"""

    enabled: bool = Field(default=True, description="是否启用 Letta runtime")
    base_url: str = Field(default="", description="Letta server base URL；为空时使用 Letta Cloud")
    api_key_env: str = Field(default="LETTA_API_KEY", description="Letta API key 环境变量名")
    server_password_env: str = Field(
        default="LETTA_SERVER_PASSWORD",
        description="本地 Letta server password 环境变量名",
    )
    agent_id: str = Field(default="", description="复用的 Letta agent id")
    agent_name: str = Field(
        default="visionox-yield-monitoring-agent",
        description="自动创建 Letta agent 时使用的稳定名称",
    )
    agent_id_cache_path: str = Field(
        default=".agent_workbench/letta_agent_id",
        description="自动创建 Letta agent 后写入的本地 agent id 缓存路径",
    )
    model: str = Field(default="my-glm-key/glm-5.1", description="Letta agent 模型名")
    embedding: str = Field(
        default="my-glm-key/text-embedding-3-large",
        description="Letta agent embedding 模型名；本地 Docker server 自动创建 Agent 时必填",
    )
    sync_memory_blocks: bool = Field(
        default=True,
        description="运行前同步 Letta memory blocks，包括 persona、runtime_policy、domain_contract、current_task",
    )
    archive_memory_candidates: bool = Field(
        default=True,
        description="将 SkillResult.memory_updates 写入 Letta archival memory/passages",
    )
    use_conversations: bool = Field(
        default=True,
        description="按 TaskSpec run_id 建立并复用 Letta conversation",
    )
    compaction_mode: str = Field(
        default="sliding_window",
        description="Letta context compaction 模式；留空则不显式配置",
    )
    compaction_clip_chars: int = Field(
        default=50000,
        description="Letta context compaction 裁剪字符数；小于等于 0 时不传入",
    )
    compaction_prompt: str = Field(
        default="Summarize operational context without inventing facts.",
        description="Letta compaction summarization prompt",
    )
    streaming: bool = Field(default=True, description="请求 Letta 返回 streaming response")
    stream_tokens: bool = Field(default=False, description="是否启用 token 级 streaming")
    background_runs: bool = Field(
        default=False,
        description="是否启用 Letta background run；默认关闭，避免改变现有同步执行语义",
    )
    timeout_seconds: int = Field(default=900, description="Letta runtime 超时秒数")
    max_tool_rounds: int = Field(default=20, description="最大 client-side tool 调用轮数")


class PydanticAIAgentRuntimeConfig(BaseModel):
    """Pydantic AI Agent Runtime 配置"""

    enabled: bool = Field(default=True, description="是否启用 Pydantic AI runtime")
    model: str = Field(default="", description="Pydantic AI runtime 模型名；为空时复用 llm.deepseek.model_name")
    base_url: str = Field(default="", description="OpenAI-compatible API base URL；为空时复用 llm.deepseek.base_url")
    api_key_env: str = Field(default="DEEPSEEK_API_KEY", description="API key 环境变量名")
    request_limit: int = Field(default=30, description="Pydantic AI 单次 run 最大请求数")
    max_tool_calls: int = Field(default=20, description="Pydantic AI 单次 run 最大工具调用数")
    tool_timeout_seconds: float | None = Field(default=None, description="单个工具调用超时秒数")
    require_tool_use_for_workflow: bool = Field(
        default=True,
        description="存在 TaskSpec workflow 时要求 Agent 至少调用一次项目工具",
    )


class AgentConfig(BaseModel):
    """Agent Runtime 配置"""

    default_runtime: str = Field(
        default="pydantic_ai",
        description="默认 runtime: pydantic_ai / letta / auto",
    )
    pydantic_ai: PydanticAIAgentRuntimeConfig = Field(
        default_factory=PydanticAIAgentRuntimeConfig
    )
    letta: LettaAgentRuntimeConfig = Field(default_factory=LettaAgentRuntimeConfig)

    @field_validator("default_runtime")
    @classmethod
    def validate_default_runtime(cls, value: str) -> str:
        allowed = {"pydantic_ai", "pydantic-ai", "pydantic", "letta", "auto"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"default_runtime 必须为 {allowed} 之一，当前值: {value}")
        return "pydantic_ai" if normalized in {"pydantic-ai", "pydantic"} else normalized


class AppConfig(BaseModel):
    """应用全局配置（根模型）"""

    app_name: str = Field(default="Yield Report Generator", description="应用名称")
    version: str = Field(default="0.1.0", description="版本号")
    debug: bool = Field(default=False, description="调试模式")
    paths: PathsConfig = Field(default_factory=PathsConfig, description="路径配置")
    llm: LlmConfig = Field(default_factory=LlmConfig, description="大模型配置")
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="日志配置")
    report: ReportConfig = Field(default_factory=ReportConfig, description="报告配置")
    agent: AgentConfig = Field(default_factory=AgentConfig, description="Agent Runtime 配置")
    products: list[ProductConfig] = Field(default_factory=list, description="产品列表")

    model_config = {"extra": "ignore"}  # 忽略未定义的额外字段
