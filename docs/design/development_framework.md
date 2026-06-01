# 开发框架约定

本项目以 V2 DDD 架构为主要演进方向，同时保留 V1 既有流水线。新增功能优先落在 `src/yield_report/` 或 `src/shared_kernel/`，只有维护旧流程时才修改 `src/excel_generator_project/`。

## 1. 分层约定

V2 分层如下：

```text
app/                         # Streamlit UI
src/shared_kernel/           # 配置、LLM、跨领域基础能力
src/yield_report/application # 用例编排
src/yield_report/core        # 领域判断、解析、策略选择
src/yield_report/infrastructure # FineReport、文件、Excel、代码执行等外部能力
```

依赖方向：

```text
app -> application -> core
app -> application -> infrastructure
core -> shared_kernel
infrastructure -> shared_kernel
```

Core 层可以使用 Shared Kernel 的统一能力，但不得直接处理业务 IO，例如 Excel 文件读写、Playwright 页面操作、FineReport 下载、临时文件执行等。

## 2. 编码纪律

- 新增 Python 模块使用 `from __future__ import annotations`。
- 函数和方法必须写类型标注。
- 优先复用项目已有工具和依赖，不随意新增第三方库。
- LLM 调用统一走 `shared_kernel.infrastructure.llm_handler.llm_manager`。
- 配置项先改 Pydantic model，再改 YAML。
- 不在 UI 层堆业务规则；UI 只做输入、反馈和编排调用。

## 3. 测试纪律

提交前运行：

```bash
uv run pytest tests/ -v --tb=short
```

按风险选择更窄的测试：

```bash
uv run pytest tests/unit/ -v --tb=short
uv run pytest tests/integration/ -v --tb=short
```

涉及配置、解析、代码执行、LLM JSON 输出清洗等逻辑时，优先补单元测试。

## 4. 质量命令

```bash
uv run pyright
uv run ruff check .
uv run ruff format .
```

Ruff 行宽配置为 100，`E501` 已忽略。不要为了满足格式做无关重排。

## 5. 文档更新

修改架构、路径、模块职责、红线或运行命令时，同步检查：

- [`.roorules`](../../.roorules)
- [`ARCHITECTURE.md`](../../ARCHITECTURE.md)
- `docs/design/` 下相关专题文档
