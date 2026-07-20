# Letta 本地部署评估与配置说明

生成日期：2026-06-22

## 结论

当前 PC 的硬件能力可以支撑本地 Letta server，前提是使用云端/API 模型做推理，不在本机跑大模型。按最多 3 人同时使用的业务 Agent 场景，Letta 本身更像状态化 Agent server + Postgres/向量检索层，CPU、内存和磁盘压力都可控。

但本机当前不能由 Codex 直接完成部署：`docker` 命令不存在，`wsl -l -v` 未返回可用 Linux 发行版列表。Windows 上推荐的 Letta Docker/Postgres 路径需要先安装 WSL2 + Docker Desktop，通常会触发管理员权限和重启。

因此本次结论是：可以本地部署，但当前机器缺少软件前置条件，本轮未启动 Letta server。建议先按本文安装 Docker Desktop 后再启动本地 Letta；如果公司环境不允许安装 Docker/WSL，则走 Letta Cloud。

## 这些配置分别是什么

`DEEPSEEK_API_KEY` 是模型供应商密钥，用于让 LLM 生成文本。它不是 Letta server 的连接凭证。

Letta runtime 需要连接到一个 Letta server：

- Letta Cloud：需要 `LETTA_API_KEY`，可选 `LETTA_AGENT_ID`。
- 本地 Letta server（无密码，仅 localhost 实验/内网单机）：需要 `LETTA_BASE_URL=http://localhost:8283`，不需要 `LETTA_API_KEY` / `LETTA_SERVER_PASSWORD`。
- 本地 Letta server（开启密码）：需要 `LETTA_BASE_URL=http://localhost:8283` 和 `LETTA_SERVER_PASSWORD=...`。
- 如果已经在 ADE 或脚本里创建过 Agent，可以提供 `LETTA_AGENT_ID`；如果不提供，项目 runtime 会尝试自动创建并缓存到 `.agent_workbench/letta_agent_id`。

项目已调整为支持本地无密码 server：只设置 `LETTA_BASE_URL` 时，`letta-client` 会以无 token 方式连接本地 server。若本地 server 需要自动创建 Agent，项目现在会要求显式配置 `agent.letta.embedding`。

## 当前 PC 能力评估

本机信息：

- 机型：Dell OptiPlex 3090
- CPU：Intel Core i5-10505，6 核 / 12 线程
- 内存：约 16 GB
- 磁盘：C 盘剩余约 22.6 GB，D 盘剩余约 265 GB
- Docker：未安装或不在 PATH
- WSL：当前未配置为可用 Linux 发行版状态

评估：

- 只跑 Letta server + Postgres + 远程 LLM API：可以。
- 3 人以内并发：可以，主要瓶颈会在外部 LLM API 延迟/限流，而不是本机硬件。
- 在本机跑大模型：不建议。当前机器没有可依赖的独立 GPU 信息，开放权重模型会明显吃内存/显存，且 Letta 官方也提示高质量 Agent harness 通常需要较强模型。
- 存储位置建议放 D 盘，例如 `D:\wzy\letta\pgdata`，避免 C 盘空间紧张。

## 推荐本地部署步骤

### 1. 安装前置条件

在管理员 PowerShell 中安装 WSL2 / Ubuntu：

```powershell
wsl --install -d Ubuntu
```

按提示重启后，安装 Docker Desktop：

```powershell
winget install -e --id Docker.DockerDesktop
```

启动 Docker Desktop，并确认：

```powershell
docker --version
docker compose version
```

### 2. 准备 Letta server 环境文件

建议新建一个只给 Docker 使用的文件，例如 `D:\wzy\letta\.env.letta`。不要把真实密钥写入仓库。

如果先用 OpenAI 作为模型和 embedding provider：

```dotenv
OPENAI_API_KEY=your_openai_key
```

如果只有 DeepSeek key：DeepSeek 官方当前文档列出的模型主要是 chat/reasoning 模型，不能假设它可直接满足 Letta Docker 的 embedding 需求。可以后续尝试 OpenAI-compatible proxy，但不建议作为第一版稳定业务部署基线。

### 3. 启动本地无密码 Letta server

只绑定到 `127.0.0.1`，避免局域网其他机器访问：

```powershell
mkdir D:\wzy\letta\pgdata
docker run -d --name visionox-letta `
  -v D:\wzy\letta\pgdata:/var/lib/postgresql/data `
  -p 127.0.0.1:8283:8283 `
  --env-file D:\wzy\letta\.env.letta `
  letta/letta:latest
```

验证：

```powershell
docker ps
curl http://localhost:8283/v1/health
```

如果要开启密码保护：

```powershell
docker run -d --name visionox-letta `
  -v D:\wzy\letta\pgdata:/var/lib/postgresql/data `
  -p 127.0.0.1:8283:8283 `
  --env-file D:\wzy\letta\.env.letta `
  -e SECURE=true `
  -e LETTA_SERVER_PASSWORD=your_local_password `
  letta/letta:latest
```

## 提供给 Codex / 项目的配置

本地无密码推荐：

```dotenv
LETTA_BASE_URL=http://localhost:8283
# 不设置 LETTA_API_KEY
# 不设置 LETTA_SERVER_PASSWORD
```

本地有密码：

```dotenv
LETTA_BASE_URL=http://localhost:8283
LETTA_SERVER_PASSWORD=your_local_password
```

已有 Agent：

```dotenv
LETTA_AGENT_ID=agent-xxxxxxxx
```

如果让项目自动创建本地 Letta Agent，需要在 `config/global.yaml` 配置模型和 embedding：

```yaml
agent:
  default_runtime: "python"
  letta:
    base_url: ""
    model: "openai/gpt-4.1"
    embedding: "openai/text-embedding-3-small"
```

注意：Letta Cloud/API 创建 Agent 时 embedding 可由 Letta 管理；Docker 本地 server 创建 Agent 时必须显式提供 `embedding`。

## client/server 兼容性

项目当前 `letta-client` 版本：

```text
letta-client 1.12.1
```

Letta 官方 v1 迁移文档说明：SDK v1 需要 Letta API 或 Docker 中运行的 Letta v0.14+；更早 Docker server 与 v1 SDK 不兼容。

由于本机尚未启动 Letta server，本轮无法读取 server 实际版本。待 Docker 安装后，建议使用 `letta/letta:latest` 启动，并做一次创建/发送消息 smoke test；如果后续 pin 版本，应把 Docker image tag 和 `letta-client` 版本一起记录在本文件或 `docs/observability.md`。

## Cloud 兜底教程

如果公司电脑不能安装 Docker/WSL，走 Letta Cloud：

1. 打开 `https://app.letta.com` 注册/登录。
2. 创建 API key。
3. 在项目 `.env` 中设置：

```dotenv
LETTA_API_KEY=your_letta_cloud_api_key
```

4. 如果在 ADE 中手动创建了 Agent，再加：

```dotenv
LETTA_AGENT_ID=agent-xxxxxxxx
```

5. `config/global.yaml` 中保持：

```yaml
agent:
  letta:
    base_url: ""
    api_key_env: "LETTA_API_KEY"
```

Cloud 路径的优点是少维护 server/Postgres/升级兼容性；缺点是需要外部账户、网络访问和数据合规确认。

## Cloud 配置验证记录

2026-06-22 已使用项目 `.env` 中的 Cloud 配置完成 smoke test，未打印任何密钥值：

- `LETTA_BASE_URL`：已设置
- `LETTA_API_KEY`：已设置
- `LETTA_AGENT_ID`：未设置，但不是必需项
- `letta-client`：1.12.1
- `agents.list(limit=1)`：成功
- Cloud 当前可见 Agent：0 个；项目随后自动创建了 `visionox-yield-monitoring-agent`
- Agent ID：已缓存到 `.agent_workbench/letta_agent_id`
- Agent 模型：`letta/auto`
- 轻量消息 smoke：成功，生成 `output/letta_cloud_message_smoke/run_summary.json` 与 `output/letta_cloud_message_smoke/outputs/letta_summary.md`

Cloud 模型列表检查结果：

- 可见模型数：63
- `letta/auto`：可用
- `openai/gpt-4.1`：未出现在当前 Cloud 账号可见模型列表中
- 可见 embedding 模型数：19，包含 `letta/letta-free`、`openai/text-embedding-3-small` 等

因此项目默认 Letta 模型已调整为 `letta/auto`。Cloud 模式下不需要你手动创建 Agent；如果 `.agent_workbench/letta_agent_id` 不存在，项目会自动创建并缓存。只有当你希望复用 Cloud UI 中手动创建的特定 Agent 时，才需要额外提供 `LETTA_AGENT_ID`。

## GLM 模型切换记录

2026-06-22 已根据 Letta Cloud 当前账号可见模型完成 GLM smoke test 与正式 Agent 更新：

- 用户期望模型：`glm-5.1`
- Letta Cloud 实际可用 BYOK handle：`my-glm-key/glm-5.1`
- 用户期望 embedding：`Embedding-3`
- Letta Cloud 实际可用 BYOK embedding handle：`my-glm-key/text-embedding-3-large`
- 临时 Agent smoke：成功；临时 Agent 已删除
- 正式 Agent `visionox-yield-monitoring-agent` 更新：成功
- 更新后正式 Agent 模型：`my-glm-key/glm-5.1`
- 更新后正式 Agent embedding：`my-glm-key/text-embedding-3-large`
- 正式 Agent 轻量消息验证：成功

项目配置已同步：

```yaml
agent:
  letta:
    model: "my-glm-key/glm-5.1"
    embedding: "my-glm-key/text-embedding-3-large"
```

## 建议

短期建议先本地部署，但不要用 pip + SQLite 作为正式业务记忆库。原因是业务 Agent 的记忆很重要，应该优先使用 Docker/Postgres 路径，便于持久化和升级。若公司策略禁止 Docker/WSL，再申请 Letta Cloud。

模型与 embedding 建议分开看：

- 对话模型：可以继续评估 DeepSeek，但 Letta Docker provider 文档未把 DeepSeek列为一线示例，需另做 OpenAI-compatible proxy 验证。
- embedding：当前只有普通 LLM key 不够稳。第一版建议申请/提供 OpenAI embedding key，或本地部署 Ollama embedding 模型并在 Letta 中显式配置；否则本地自动创建 Agent 会失败。

## 已执行的项目侧改动

- 增加 `agent.letta.embedding` 配置字段。
- 本地 `LETTA_BASE_URL` 模式支持无密码连接。
- 本地自动创建 Agent 时，如果没有 embedding，会返回结构化失败而不是让 API 字段不兼容错误外溢。
- Cloud `LETTA_BASE_URL` 不再被误判为本地 server；只有 localhost/127.0.0.1/::1 才要求本地 embedding。
- Letta 默认模型调整为 `letta/auto`，匹配当前 Cloud 账号可见模型列表。
- 聚焦验证已通过：

```text
uv run pytest tests/unit/agent/test_letta_runtime.py tests/unit/test_config_loader.py::TestAppConfigModel::test_agent_letta_config -v --tb=short
uv run ruff check src/yield_report/agent/letta_runtime.py src/yield_report/agent/runtime_adapter.py src/shared_kernel/config_model.py tests/unit/agent/test_letta_runtime.py tests/unit/test_config_loader.py
uv run pyright src/yield_report/agent/letta_runtime.py src/yield_report/agent/runtime_adapter.py src/shared_kernel/config_model.py tests/unit/agent/test_letta_runtime.py tests/unit/test_config_loader.py
```

## 参考资料

- Letta Docker server 文档：https://docs.letta.com/guides/docker
- Letta Docker model providers：https://docs.letta.com/guides/docker/providers
- Letta Python API library：https://docs.letta.com/api/python
- Letta API v1 migration guide：https://docs.letta.com/api-overview/v1-migration-guide
- Letta Docker Hub image：https://hub.docker.com/r/letta/letta
- DeepSeek Models & Pricing：https://api-docs.deepseek.com/quick_start/pricing
- DeepSeek List Models API：https://api-docs.deepseek.com/api/list-models
