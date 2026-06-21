# Task18 Letta Runtime Refactor Findings

## Local Interfaces

- `RuntimeRouter.run_spec(spec, context, requested_runtime=...)` is the public routing interface.
- `RuntimeRouter` now accepts an optional `letta_runtime` and `default_runtime`.
- `auto` now follows `agent.default_runtime`; `config/global.yaml` keeps the gray-release default at `python`.
- `PythonSkillRuntime.run_spec` wraps `build_default_runtime().run_spec`.
- `RunStore` owns the run-scoped contract: `spec.yaml`, `trace.jsonl`, `outputs/`, `memory_candidates.json`, `run_summary.json`.
- Letta agent id persistence now uses `.agent_workbench/letta_agent_id`, which is already ignored by Git, so the memory container can be reused without manually editing config each run.
- `DEEPSEEK_API_KEY` is a model-provider key, not a Letta runtime connection credential. It may power project LLM calls or a configured local Letta server, but the adapter still needs Letta Cloud (`LETTA_API_KEY`) or local server (`LETTA_BASE_URL` + `LETTA_SERVER_PASSWORD`).
- The adapter now supports local server credentials from `.env`: if `LETTA_BASE_URL` is set and `LETTA_API_KEY` is absent, it uses `LETTA_SERVER_PASSWORD`.
- The adapter now also supports no-password localhost mode: if `LETTA_BASE_URL` is set and neither `LETTA_API_KEY` nor `LETTA_SERVER_PASSWORD` is present, it connects with `api_key=None`.
- Local Docker server auto-create requires an explicit embedding model. The project now exposes `agent.letta.embedding` and returns a structured `letta.unavailable` failure before calling Letta if local auto-create has no embedding.
- Existing runtime tests use lightweight fake runtime classes and `SkillResult` through public interfaces.

## Test Findings

- First tracer bullet should add explicit `runtime=letta` router behavior, avoiding OMP/Python.
- `uv run pytest tests/unit/agent/test_letta_runtime.py -v --tb=short` passes with router, config, fake-client, tool-loop, missing-key, max-rounds, and CLI coverage.
- `uv run pytest tests/unit/agent tests/unit/skills tests/unit/test_config_loader.py::TestAppConfigModel::test_agent_letta_config -v --tb=short` passes with 67 tests.
- After Task1-fix, `uv run pytest tests/unit/agent tests/unit/skills tests/unit/test_config_loader.py::TestAppConfigModel::test_agent_letta_config -v --tb=short` passes with 70 tests.
- Touched-file `ruff check` passes.
- Touched production/test files pass `uv run pyright src/yield_report/agent/letta_runtime.py src/yield_report/agent/runtime_adapter.py src/shared_kernel/config_model.py scripts/run_task_spec.py tests/unit/agent/test_letta_runtime.py tests/unit/test_config_loader.py`.
- Full `ruff check .` is not a valid regression signal yet because it fails on unrelated existing lint debt in legacy scripts and modules.
- Full `pyright` now runs after adding the dev dependency, but reports unrelated existing type debt across legacy scripts/modules and older tests.

## Runtime / Black-Box Findings

- Smoke spec path: `specs/runs/run-letta-m678-monthly-trend-smoke-20260622/spec.yaml`.
- Environment currently has no `LETTA_API_KEY`, `LETTA_AGENT_ID`, `LETTA_SERVER_PASSWORD`, or `LETTA_BASE_URL`.
- `http://localhost:8283/v1/health` is unreachable, so there is no detectable default local Letta server.
- Real black-box execution is blocked at Letta client creation: `Missing Letta API key env var: LETTA_API_KEY`.
- Hardware assessment: Dell OptiPlex 3090, i5-10505 6c/12t, ~16 GB RAM, D drive ~265 GB free. This is sufficient for Letta server + Postgres + remote/API LLM usage for <=3 users.
- Deployment blocker: `docker` is not installed or not in PATH, and `wsl -l -v` did not show a usable Linux distro. Docker/Postgres deployment needs WSL2 + Docker Desktop before the local server can be started.
- Letta Cloud GLM finding: user-visible model name `glm-5.1` maps to BYOK handle `my-glm-key/glm-5.1` in the current Cloud account. Requested `Embedding-3` maps to `my-glm-key/text-embedding-3-large` for the tested successful path.
- The Cloud Agent can be updated in place with `client.agents.update(agent_id=..., model=..., embedding=...)`; existing `.agent_workbench/letta_agent_id` remains valid after model/embedding changes.
- The adapter cannot be considered fully accepted until the same smoke spec runs against a configured Letta agent and produces `trace.jsonl`, `run_summary.json`, `memory_candidates.json`, and `outputs/letta_summary.md`.
