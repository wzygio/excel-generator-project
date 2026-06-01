# Shared Kernel 设计

Shared Kernel 位于 [`src/shared_kernel/`](../../src/shared_kernel/)，承载跨领域复用且需要统一治理的基础能力。目前包含配置体系和 LLM 调用管理；日志初始化在 [`app/utils/logger_setup.py`](../../app/utils/logger_setup.py)。

## 1. 职责边界

Shared Kernel 负责：

- 强类型配置模型与配置加载。
- LLM 供应商调用封装。
- 与业务无关的全局基础能力。

Shared Kernel 不负责：

- Excel 源表业务解析。
- FineReport 页面自动化。
- 良率 Gap、异常、趋势等领域算法。
- V1 报告生成与富文本样式注入。

## 2. 配置模型

核心文件：

- [`config_model.py`](../../src/shared_kernel/config_model.py)
- [`config.py`](../../src/shared_kernel/config.py)

`AppConfig` 是根配置模型，主要包含：

- `paths`: 资源、缓存、日志、输出、模板路径。
- `llm`: DeepSeek/Gemini 供应商配置。
- `logging`: 日志级别与保留策略。
- `report`: 报告模块与分析参数。
- `products`: 产品级配置列表。

加载优先级：

```text
Pydantic 默认值
    ↓
config/global.yaml
    ↓
config/products/*.yaml
    ↓
.env 环境变量
```

`ConfigLoader` 使用单例模式，模块级实例为 `config`。新增配置项必须先扩展 `AppConfig` 或其子模型，再更新 YAML。

## 3. LLMManager

核心文件：[`llm_handler.py`](../../src/shared_kernel/infrastructure/llm_handler.py)

`LLMManager` 是项目唯一的 LLM API 调用入口：

- `chat()`: 支持 DeepSeek 与 Gemini。
- `chat_stream()`: 当前仅支持 DeepSeek。
- `clear_clients()`: 清理客户端缓存。

约束：

- 禁止业务代码直接实例化 OpenAI/Gemini 客户端。
- 业务 Prompt 不放在 `llm_handler.py` 内；由调用方或领域模块提供。
- API Key 从 `.env` 读取，首次调用时懒加载。

## 4. 日志

日志初始化在 [`app/utils/logger_setup.py`](../../app/utils/logger_setup.py)。当前策略是按领域和级别分离日志文件，并使用按天轮转。

涉及日志配置时，优先从 `AppConfig.logging` 扩展，不要在业务模块中散落硬编码。

## 5. 修改清单

修改 Shared Kernel 前请检查：

- 是否会影响 V2 UI 初始化。
- 是否会影响 `QueryParser`、`AnalysisStrategySelector`、`AnalysisOrchestrator` 的 LLM 调用。
- 是否需要补充或更新 `tests/unit/test_config_loader.py`。
- 是否需要更新 `.env` 示例或 `config/global.yaml`。
