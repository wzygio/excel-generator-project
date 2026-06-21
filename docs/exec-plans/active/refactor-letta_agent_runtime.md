# Refactor Plan: Letta Agent Runtime

Status: active  
Created: 2026-06-22  
Source research: `D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev\letta_agent_runtime_migration_guide_2026-06-22.md`

## Goal

Replace the OMP-first Agent Runtime path with a Letta-backed runtime adapter while preserving the current project contracts:

```text
TaskSpec -> RuntimeRouter -> Skill Tool -> SkillResult -> Trace / Memory / Output
```

Letta should provide the stateful Agent loop, tool selection, memory blocks, archival memory, conversations, and long-running execution support. The project must continue to own FineReport/Excel IO, run directories, trace files, artifacts, and typed business memory.

## Current State

Relevant current modules:

- `src/yield_report/agent/runtime_adapter.py`
  - `auto` currently routes to OMP.
  - explicit `python` routes to `PythonSkillRuntime`.
- `src/yield_report/agent/omp_runtime.py`
  - invokes local OMP CLI and maps the result back to `SkillResult`.
- `src/yield_report/agent/runtime.py`
  - deterministic Python Skill runtime.
  - executes registered skills and writes trace/summary/memory candidates.
- `src/yield_report/agent/run_store.py`
  - owns `spec.yaml`, `trace.jsonl`, `outputs/`, `memory_candidates.json`, `run_summary.json`.
- `src/yield_report/agent/spec_model.py`
  - owns `TaskSpec`, `SkillCall`, `SkillResult`, `RunContext`, `MemoryCandidate`.
- `src/yield_report/agent/memory.py`
  - facade over current analysis memory store.

## Target Architecture

```text
RuntimeRouter
  ├─ python        -> PythonSkillRuntime
  ├─ omp           -> legacy / fallback only
  └─ letta         -> LettaRuntime
                       ├─ Letta agent memory
                       ├─ client-side tools
                       ├─ project Skills
                       └─ RunStore / TraceWriter / SkillResult
```

Runtime rules:

1. `requested_runtime="letta"` uses Letta.
2. `requested_runtime="python"` keeps deterministic Skill execution.
3. `requested_runtime="omp"` keeps the legacy OMP path during transition.
4. `auto` should not become Letta-first until tests and a real smoke pass.
5. All actual FineReport, Excel, filesystem, and artifact work must stay inside project Skills.

## Why Client-Side Tools

Use Letta client-side tools rather than server tools for the first implementation.

Reasons:

- FineReport RPA depends on local network, browser/session configuration, and `.env` secrets.
- Excel files and generated artifacts should remain under local project-controlled paths.
- Letta Cloud or server sandbox should not receive raw enterprise Excel workbooks or credentials.
- Project Skills already expose typed Python contracts.

Letta should see only:

- task summary;
- safe schema/metadata;
- client-side tool schema;
- structured tool return payloads;
- artifact paths and summaries.

## Phases

| Phase | Status | Objective | Validation |
| --- | --- | --- | --- |
| 0 | pending | Add Letta dependency/config without changing default runtime | import/config tests |
| 1 | pending | Add `LettaRuntime` adapter with mocked Letta client | unit tests |
| 2 | pending | Expose project Skills as Letta client-side tools | unit tests for tool dispatch |
| 3 | pending | Wire `RuntimeRouter` explicit `runtime=letta` | router tests |
| 4 | pending | Add memory synchronization between project memory and Letta memory | memory tests / artifact checks |
| 5 | pending | Run real Letta smoke with one data-analysis task | `scripts/run_task_spec.py --runtime letta` smoke |
| 6 | pending | Decide whether `auto` should become Letta-first | accepted architecture update |

## Phase 0: Dependency And Config

Add SDK:

```powershell
uv add letta-client
```

Update Pydantic config model before changing `config/global.yaml`.

Suggested config model:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class LettaRuntimeConfig(BaseModel):
    enabled: bool = Field(default=False)
    base_url: str = Field(default="")
    api_key_env: str = Field(default="LETTA_API_KEY")
    server_password_env: str = Field(default="LETTA_SERVER_PASSWORD")
    agent_id: str = Field(default="")
    model: str = Field(default="openai/gpt-4.1")
    timeout_seconds: int = Field(default=900)
    max_tool_rounds: int = Field(default=20)
```

Suggested YAML:

```yaml
agent:
  default_runtime: python
  letta:
    enabled: true
    base_url: ""
    api_key_env: LETTA_API_KEY
    server_password_env: LETTA_SERVER_PASSWORD
    agent_id: ""
    agent_name: visionox-yield-monitoring-agent
    agent_id_cache_path: .agent_workbench/letta_agent_id
    model: openai/gpt-4.1
    timeout_seconds: 900
    max_tool_rounds: 20
```

Credential meaning:

- `DEEPSEEK_API_KEY` is a model-provider credential. Project Skills can use it through the existing LLM manager, and a local Letta server may also use it as an upstream model key if configured that way.
- `LETTA_API_KEY` is a Letta Cloud/API credential. It authenticates this runtime adapter to the Letta service.
- `LETTA_SERVER_PASSWORD` is the local Letta server password. The adapter uses it when `LETTA_BASE_URL` or `agent.letta.base_url` points at a local/server endpoint.
- `LETTA_AGENT_ID` is optional. If absent, the adapter creates a project-scoped Letta agent and caches its id in `.agent_workbench/letta_agent_id`.

Cloud `.env`:

```env
LETTA_API_KEY=...
# Optional; omit to let the runtime create/cache an agent id.
LETTA_AGENT_ID=agent-...
```

Local Letta server `.env`:

```env
LETTA_BASE_URL=http://localhost:8283
LETTA_SERVER_PASSWORD=...
DEEPSEEK_API_KEY=...
# Optional; omit to let the runtime create/cache an agent id.
LETTA_AGENT_ID=agent-...
```

If using a local Letta server through YAML instead of `LETTA_BASE_URL`:

```yaml
agent:
  letta:
    base_url: "http://localhost:8283"
    api_key_env: LETTA_SERVER_PASSWORD
```

## Phase 1: LettaRuntime Adapter

Add `src/yield_report/agent/letta_runtime.py`.

Initial implementation sketch:

```python
from __future__ import annotations

import json
import os
from typing import Any

import letta_client
from letta_client import Letta
from pydantic import BaseModel

from yield_report.agent.registry import build_default_runtime
from yield_report.agent.spec_model import (
    ArtifactRef,
    RunContext,
    SkillCall,
    SkillError,
    SkillResult,
    TaskSpec,
)
from yield_report.agent.trace import TraceEvent


class LettaRuntimeConfig(BaseModel):
    base_url: str = ""
    api_key_env: str = "LETTA_API_KEY"
    agent_id: str = ""
    model: str = "openai/gpt-4.1"
    max_tool_rounds: int = 20


class LettaRuntimeUnavailableError(Exception):
    pass


class LettaRuntime:
    runtime_name = "letta"

    def __init__(self, config: LettaRuntimeConfig | None = None) -> None:
        self.config = config or LettaRuntimeConfig()
        self.project_runtime = build_default_runtime()

    def _client(self) -> Letta:
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise LettaRuntimeUnavailableError(
                f"Missing Letta API key env var: {self.config.api_key_env}"
            )
        if self.config.base_url:
            return Letta(base_url=self.config.base_url, api_key=api_key)
        return Letta(api_key=api_key)

    def run_spec(self, spec: TaskSpec, context: RunContext) -> list[SkillResult]:
        client = self._client()
        agent_id = self.config.agent_id or os.getenv("LETTA_AGENT_ID")
        if not agent_id:
            agent_id = self._create_agent(client).id

        self._write_trace(context, "letta_runtime", "started", "Sending TaskSpec to Letta")
        prompt = self._build_prompt(spec, context)

        try:
            response = client.agents.messages.create(
                agent_id=agent_id,
                messages=[{"role": "user", "content": prompt}],
                client_tools=PROJECT_CLIENT_TOOLS,
            )
            response = self._tool_loop(client, agent_id, response, spec, context)
        except letta_client.APIError as exc:
            return [
                self._failed_result(
                    code="letta.api_error",
                    message=str(exc),
                    details={"exception_type": type(exc).__name__},
                )
            ]
        except Exception as exc:
            return [
                self._failed_result(
                    code="letta.runtime_error",
                    message=str(exc),
                    details={"exception_type": type(exc).__name__},
                )
            ]

        summary = self._assistant_text(response)
        summary_path = context.output_dir / "letta_summary.md"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary or "Letta runtime completed.", encoding="utf-8")

        self._write_trace(context, "letta_runtime", "succeeded", summary[:500])
        return [
            SkillResult(
                skill_name="letta_agent",
                success=True,
                summary=summary or "Letta runtime completed.",
                artifacts=[
                    ArtifactRef(
                        kind="markdown",
                        path=summary_path,
                        description="Letta runtime summary",
                    )
                ],
                data={
                    "runtime": self.runtime_name,
                    "letta_agent_id": agent_id,
                },
            )
        ]

    def _tool_loop(
        self,
        client: Letta,
        agent_id: str,
        response: Any,
        spec: TaskSpec,
        context: RunContext,
    ) -> Any:
        for round_index in range(self.config.max_tool_rounds):
            approvals = []
            for msg in getattr(response, "messages", []) or []:
                if getattr(msg, "message_type", "") != "approval_request_message":
                    continue
                tool_call = getattr(msg, "tool_call", None)
                if tool_call is None:
                    continue
                tool_return, status = self._execute_client_tool(tool_call, spec, context)
                approvals.append(
                    {
                        "type": "tool",
                        "tool_call_id": tool_call.tool_call_id,
                        "tool_return": tool_return,
                        "status": status,
                    }
                )

            if not approvals:
                return response

            self._write_trace(
                context,
                "letta_tool_round",
                "succeeded",
                f"round={round_index + 1}, approvals={len(approvals)}",
            )
            response = client.agents.messages.create(
                agent_id=agent_id,
                messages=[{"type": "approval", "approvals": approvals}],
                client_tools=PROJECT_CLIENT_TOOLS,
            )

        raise RuntimeError(f"Letta exceeded max_tool_rounds={self.config.max_tool_rounds}")
```

Implementation details to decide during coding:

- Whether to auto-create agent or require configured `LETTA_AGENT_ID`.
- How to persist Letta `run_id`, message ids, and tool call ids in `run_summary.json`.
- Whether to make client-side tool schema static or generated from Pydantic models.
- How to stream events to CopilotKit UI.

## Phase 2: Client-Side Tools

Expose only business tools at first:

```python
PROJECT_CLIENT_TOOLS = [
    {
        "name": "yield_report_download",
        "description": (
            "Download or locate OLED yield source reports through the project's "
            "report_download Skill. Use this before analysis when source files are missing or stale."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "report_type": {"type": "string", "description": "daily_yield or batch_yield"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                "product_models": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Product model list such as M626 or M678",
                },
                "filters": {"type": "object", "description": "Optional report filters"},
            },
            "required": ["report_type"],
        },
    },
    {
        "name": "yield_data_analysis",
        "description": (
            "Analyze local Excel source files with the project's data_analysis Skill. "
            "Use this for trends, deterioration, gap, and anomaly reason analysis."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Local Excel file path"},
                "product_models": {"type": "array", "items": {"type": "string"}},
                "metrics": {"type": "array", "items": {"type": "string"}},
                "time_grain": {"type": "string", "description": "day, week, month, batch"},
                "requested_periods": {"type": "integer"},
                "analysis_goal": {"type": "string"},
            },
            "required": ["analysis_goal"],
        },
    },
    {
        "name": "yield_daily_report",
        "description": (
            "Generate final daily report artifacts with the project's daily_report Skill. "
            "Use only after source reports and analysis are ready."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "analysis_artifact_path": {"type": "string"},
                "output_name": {"type": "string"},
                "report_date": {"type": "string"},
                "product_models": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["report_date"],
        },
    },
]
```

Dispatch sketch:

```python
def _execute_client_tool(
    self,
    tool_call: Any,
    spec: TaskSpec,
    context: RunContext,
) -> tuple[str, str]:
    name = tool_call.name
    args = json.loads(tool_call.arguments or "{}")
    skill_name = {
        "yield_report_download": "report_download",
        "yield_data_analysis": "data_analysis",
        "yield_daily_report": "daily_report",
    }.get(name)
    if skill_name is None:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False), "error"

    call = SkillCall(
        id=f"letta_{name}",
        skill=skill_name,
        input=args,
    )
    result = self.project_runtime.run_call(call, context)
    payload = result.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, default=str), (
        "success" if result.success else "error"
    )
```

Validation requirements:

- Validate tool args with each Skill's Pydantic request model.
- Reject absolute paths outside allowed project roots.
- Never expose arbitrary shell or unrestricted filesystem tools.
- Serialize only safe summaries and artifact paths back to Letta.

## Phase 3: RuntimeRouter Wiring

Modify `src/yield_report/agent/runtime_adapter.py`:

```python
from yield_report.agent.letta_runtime import LettaRuntime, LettaRuntimeUnavailableError


class RuntimeRouter:
    def __init__(
        self,
        python_runtime: PythonSkillRuntime | None = None,
        omp_runtime: OmpJsonRuntime | None = None,
        letta_runtime: LettaRuntime | None = None,
    ) -> None:
        self.python_runtime = python_runtime or PythonSkillRuntime()
        self.omp_runtime = omp_runtime or OmpJsonRuntime()
        self.letta_runtime = letta_runtime or LettaRuntime()

    def run_spec(
        self,
        spec: TaskSpec,
        context: RunContext,
        requested_runtime: str = "auto",
    ) -> RuntimeRunResult:
        requested = (requested_runtime or "auto").lower().strip()

        if requested == "letta":
            return self._run_letta(spec, context)
        if requested in {"omp", "pi"}:
            return self._run_omp(spec, context)
        if requested == "python":
            results = self.python_runtime.run_spec(spec, context)
            return RuntimeRunResult(runtime="python", results=results)

        runtime_hint = str(spec.constraints.get("runtime") or "").lower()
        if runtime_hint == "letta":
            return self._run_letta(spec, context)
        if runtime_hint in {"omp", "pi"}:
            return self._run_omp(spec, context)

        if requested == "auto":
            results = self.python_runtime.run_spec(spec, context)
            return RuntimeRunResult(runtime="python", results=results)

        results = self.python_runtime.run_spec(spec, context)
        return RuntimeRunResult(runtime="python", results=results)

    def _run_letta(self, spec: TaskSpec, context: RunContext) -> RuntimeRunResult:
        try:
            results = self.letta_runtime.run_spec(spec, context)
        except LettaRuntimeUnavailableError as exc:
            raise RuntimeError(str(exc)) from exc
        return RuntimeRunResult(runtime="letta", results=results)
```

Gray release rule:

- First release: explicit `--runtime letta` only.
- Second release: allow `spec.constraints.runtime=letta`.
- Third release: if accepted, `auto -> letta first -> python fallback`.

## Phase 4: Memory Integration

Letta memory should not replace project typed memory.

Run-start flow:

1. Retrieve relevant project typed memory by report type, product model, metrics, and time grain.
2. Build a compact safe memory context.
3. Update a Letta current-context block or include the context in the run prompt.

Sketch:

```python
def build_memory_context(context: RunContext, spec: TaskSpec) -> str:
    return (
        "已确认规则：\n"
        "- 源文件结束日期落后请求日期超过 1 天时，需要重新下载。\n"
        "- 3 个月趋势分析若源表只有 2 个月数据，需要重新下载并设置 month_count=3。\n"
    )
```

Run-end flow:

1. Keep writing `memory_candidates.json`.
2. Optionally write a safe run lesson to Letta archival memory.
3. Do not store secrets or full raw Excel data.
4. Business-impacting memory remains `pending` until confirmed by project rules or user correction.

Sketch:

```python
client.agents.passages.insert(
    agent_id=agent_id,
    content=(
        f"run_id={context.run_id}; "
        "M626 weekly yield deterioration analysis succeeded; "
        "source report was refreshed because local file was stale."
    ),
    tags=["yield", "run_lesson", context.run_id],
)
```

## Phase 5: Long-Running Execution

For FineReport download and multi-file analysis, use streaming/background mode after the synchronous loop works.

Sketch:

```python
stream = client.agents.messages.create(
    agent_id=agent_id,
    messages=[{"role": "user", "content": prompt}],
    client_tools=PROJECT_CLIENT_TOOLS,
    streaming=True,
    stream_tokens=True,
    background=True,
)

run_id = None
last_seq_id = None
for chunk in stream:
    if hasattr(chunk, "run_id") and hasattr(chunk, "seq_id"):
        run_id = chunk.run_id
        last_seq_id = chunk.seq_id
    # Write chunk metadata to trace/UI stream.

for chunk in client.runs.stream(run_id, starting_after=last_seq_id):
    # Resume after disconnect.
    pass
```

If a background run emits a client-side tool call, the backend must still execute the local Skill and submit approval/tool return.

## Security Rules

- Do not send `.env`, FineReport credentials, cookies, tokens, or portal sessions to Letta.
- Do not send complete Excel workbooks to Letta Cloud.
- Only expose whitelisted client-side business tools.
- Keep raw artifacts under project-controlled `specs/runs/<run_id>/outputs/`.
- Tool return payloads should contain summaries, structured results, warnings, errors, and artifact refs.
- Use path whitelisting for `resources/`, `downloads/`, `output/`, and run-specific directories.
- Keep `runtime_policy` memory block read-only.
- Any high-risk tool should require approval before execution.

## Tests

Add:

```text
tests/unit/agent/test_letta_runtime.py
```

Coverage:

- Missing API key raises or returns `LettaRuntimeUnavailableError`.
- `run_spec()` builds expected TaskSpec prompt.
- `run_spec()` passes the three client-side tool schemas.
- `approval_request_message` dispatches to the correct project Skill.
- successful SkillResult returns Letta tool approval with status `success`.
- failed SkillResult returns Letta tool approval with status `error`.
- unknown tool returns structured error.
- exceeding `max_tool_rounds` returns structured failure.
- final assistant message maps to `SkillResult.summary`.
- trace includes `letta_runtime` and `letta_tool_round`.
- `RuntimeRouter` explicit `requested_runtime="letta"` selects Letta.
- `requested_runtime="python"` still avoids Letta.

Commands:

```powershell
uv run pytest tests/unit/agent/test_letta_runtime.py -v --tb=short
uv run pytest tests/unit/agent tests/unit/skills -v --tb=short
uv run ruff check .
uv run pyright
```

Real smoke, after environment is configured:

```powershell
$env:LETTA_API_KEY="..."
$env:LETTA_AGENT_ID="agent-..."
uv run python scripts/run_task_spec.py --spec specs/runs/<run_id>/spec.yaml --runtime letta
```

Smoke acceptance:

- `trace.jsonl` exists.
- `run_summary.json` exists.
- `outputs/letta_summary.md` exists.
- Letta initiated at least one project Skill call.
- local SkillResult was used in final Chinese summary.
- Letta agent memory can be inspected through ADE or API.

## Rollout Checklist

- [ ] User confirms this active execution plan.
- [ ] Add dependency and config model.
- [ ] Add `letta_runtime.py`.
- [ ] Add client-side tool schemas and dispatch.
- [ ] Wire explicit `runtime=letta`.
- [ ] Add unit tests with mock Letta client.
- [ ] Run focused Agent/Skill tests.
- [ ] Run one real Letta smoke.
- [ ] Ask user to confirm whether Letta architecture is accepted.
- [ ] If accepted, update `ARCHITECTURE.md` and related agent docs.
- [ ] Decide whether `auto` should become Letta-first.
