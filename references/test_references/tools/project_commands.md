# Project Commands

## Workbench

```bash
cd ui/copilotkit-agent
npm run dev
```

## Python Tests

```bash
uv run pytest tests/ -v --tb=short
uv run pytest tests/unit/agent tests/unit/skills -v --tb=short
```

## TaskSpec

```bash
uv run python scripts/create_daily_report_spec.py --goal "生成 M678 今天良率日报" --print-path
uv run python scripts/run_task_spec.py --spec specs/runs/<run_id>/spec.yaml --runtime auto
```

## Quality

```bash
uv run ruff check .
uv run pyright
```

## Harness

```bash
uv run python scripts/harness_check.py
uv run python scripts/harness_check.py --write-audit
```

Format only when the task calls for formatting or the touched files need it:

```bash
uv run ruff format .
```

## Dependencies

```bash
uv sync
uv add <package-name>
uv add --dev <package-name>
```
