# 智能查询 Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 Streamlit 主应用中新增 Tab 4「智能查询」，用户通过自然语言描述需求，系统自动从 `docs/project_files/` 中的 Excel 文件提取 schema、LLM 动态生成 pandas 代码并执行，结果以表格/文本形式渲染到前端。

**Architecture:** 三层结构 — `code_generator.py`（Schema 提取 + 通过 `claude` CLI 生成 pandas 代码）、`code_executor.py`（写入临时 .py 文件 + `subprocess.run` 操作系统级安全执行 + stdout→DataFrame 解析）、`app/main.py`（Tab 4 UI 集成，含代码预览 toggle、`st.dataframe()` 渲染、磁盘持久化查询历史）。文件选择器从 `docs/project_files/` 扫描所有 .xlsx/.xls 文件。

**Key Design Decisions:**
- **Claude CLI** 生成代码而非 LLMManager API — Claude 代码生成质量更高，推理能力更强
- **临时 .py 文件执行**而非 `StringIO` 重定向 — 操作系统级 `capture_output=True` 不会漏掉 C 扩展层输出
- **`st.dataframe()`** 渲染结果 — 可排序/筛选的动态表格，优于纯文本
- **磁盘持久化**查询历史到 `docs/query_history.json` — 防止 Streamlit rerun 丢失记录

**Tech Stack:** Streamlit, pandas, openpyxl, Claude CLI (subprocess), pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `tests/analyze_yield/__init__.py` | Create | 包入口，导出公共接口 |
| `tests/analyze_yield/code_generator.py` | Create | Excel schema 提取 + LLM prompt 构建 + 代码生成 |
| `tests/analyze_yield/code_executor.py` | Create | 生成代码的安全执行 + stdout/DataFrame 捕获 |
| `tests/unit/test_code_generator.py` | Create | code_generator 单元测试 |
| `tests/unit/test_code_executor.py` | Create | code_executor 单元测试 |
| `app/main.py` | Modify | 新增 Tab 4 智能查询 UI |

---

### Task 1: Package Initialization

**Files:**
- Create: `tests/analyze_yield/__init__.py`

- [ ] **Step 1: Write the package init**

```python
"""tests/analyze_yield - 智能查询模块

通过自然语言查询 Excel 文件的工具模块。
"""
```

- [ ] **Step 2: Commit**

```bash
git add tests/analyze_yield/__init__.py
git commit -m "feat: add analyze_yield package skeleton"
```

---

### Task 2: Code Generator — Schema Extraction

**Files:**
- Create: `tests/analyze_yield/code_generator.py`
- Test: `tests/unit/test_code_generator.py`

- [ ] **Step 1: Write the failing test for `extract_schema`**

```python
"""test_code_generator.py - CodeGenerator 单元测试"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.analyze_yield.code_generator import CodeGenerator, extract_schema, build_prompt


class TestExtractSchema:
    """测试 Excel schema 提取。"""

    def test_extract_schema_from_valid_xlsx(self, tmp_path: Path):
        """从有效的 xlsx 文件提取 schema 字符串。"""
        file_path = tmp_path / "test.xlsx"
        df = pd.DataFrame({
            "日期": ["2026-05-01", "2026-05-02"],
            "良率": [0.95, 0.96],
            "产品型号": ["3TED01", "3TED02"],
        })
        df.to_excel(file_path, index=False)

        result = extract_schema(file_path)
        assert "日期" in result
        assert "良率" in result
        assert "产品型号" in result
        assert "2026-05-01" in result

    def test_extract_schema_returns_max_5_rows(self, tmp_path: Path):
        """schema 最多展示 5 行数据。"""
        file_path = tmp_path / "test.xlsx"
        df = pd.DataFrame({"col": range(10)})
        df.to_excel(file_path, index=False)

        result = extract_schema(file_path)
        # 表头 + 最多 5 行 → 应该有 6 行文本
        lines = result.strip().split("\n")
        assert len(lines) <= 6

    def test_extract_schema_file_not_found_raises(self, tmp_path: Path):
        """文件不存在时抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            extract_schema(tmp_path / "nonexistent.xlsx")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_code_generator.py::TestExtractSchema -v`
Expected: FAIL with "ModuleNotFoundError" or "cannot import"

- [ ] **Step 3: Write minimal implementation**

```python
"""code_generator.py - LLM 驱动的 pandas 代码生成器"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def extract_schema(file_path: Path, nrows: int = 5) -> str:
    """从 Excel 文件提取前 N 行的 schema 信息。

    Args:
        file_path: Excel 文件路径
        nrows: 展示的数据行数

    Returns:
        表头和数据抽样的字符串表示

    Raises:
        FileNotFoundError: 文件不存在
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    df = pd.read_excel(file_path, nrows=nrows)
    return df.to_string()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_code_generator.py::TestExtractSchema -v`
Expected: all 3 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/analyze_yield/code_generator.py tests/unit/test_code_generator.py
git commit -m "feat: add extract_schema for Excel schema extraction"
```

---

### Task 3: Code Generator — Prompt Building & LLM Code Generation

**Files:**
- Modify: `tests/analyze_yield/code_generator.py`
- Modify: `tests/unit/test_code_generator.py`

- [ ] **Step 1: Write the failing test for `build_prompt` and `generate_code`**

Append to `tests/unit/test_code_generator.py`:

At the top of the file, add `import subprocess` after the existing imports. Then append the test classes:

```python
class TestBuildPrompt:
    """测试 prompt 构建。"""

    def test_build_prompt_includes_schema(self):
        """prompt 应包含传入的 schema 文本。"""
        schema = "col1  col2\n1     2"
        demand = "查询col1最大值"

        prompt = build_prompt(schema, demand, "/data/test.xlsx")
        assert "col1" in prompt
        assert "查询col1最大值" in prompt
        assert "/data/test.xlsx" in prompt

    def test_build_prompt_includes_code_constraints(self):
        """prompt 应包含代码生成约束。"""
        prompt = build_prompt("schema", "demand", "file.xlsx")
        assert "print" in prompt.lower()


class TestGenerateCode:
    """测试通过 Claude CLI 生成代码。"""

    @pytest.fixture
    def gen(self) -> CodeGenerator:
        return CodeGenerator()

    def test_generate_code_returns_string(self, gen: CodeGenerator, monkeypatch):
        """generate_code 应返回非空字符串。"""
        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args, returncode=0, stdout="print(df.describe())", stderr=""
            )

        monkeypatch.setattr(
            "tests.analyze_yield.code_generator.subprocess.run",
            mock_run,
        )

        result = gen.generate_code(
            schema="col1\n1\n2",
            user_demand="统计col1",
            file_path="/data/test.xlsx",
        )
        assert "print" in result

    def test_generate_code_cleans_markdown(self, gen: CodeGenerator, monkeypatch):
        """应清理 Claude 返回中的 ```python 标记。"""
        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args, returncode=0,
                stdout="```python\nprint(df.head())\n```", stderr=""
            )

        monkeypatch.setattr(
            "tests.analyze_yield.code_generator.subprocess.run",
            mock_run,
        )

        result = gen.generate_code("schema", "demand", "file.xlsx")
        assert "```" not in result
        assert result.strip() == "print(df.head())"

    def test_generate_code_claude_failure_raises(self, gen: CodeGenerator, monkeypatch):
        """Claude CLI 非零退出码时抛出 RuntimeError。"""
        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args, returncode=1, stdout="", stderr="Claude error"
            )

        monkeypatch.setattr(
            "tests.analyze_yield.code_generator.subprocess.run",
            mock_run,
        )

        with pytest.raises(RuntimeError, match="Claude CLI 返回非零退出码"):
            gen.generate_code("schema", "demand", "file.xlsx")

    def test_generate_code_empty_response_raises(self, gen: CodeGenerator, monkeypatch):
        """Claude 返回空字符串时抛出 RuntimeError。"""
        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args, returncode=0, stdout="", stderr=""
            )

        monkeypatch.setattr(
            "tests.analyze_yield.code_generator.subprocess.run",
            mock_run,
        )

        with pytest.raises(RuntimeError, match="Claude CLI 返回了空代码"):
            gen.generate_code("schema", "demand", "file.xlsx")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_code_generator.py::TestBuildPrompt tests/unit/test_code_generator.py::TestGenerateCode -v`
Expected: FAIL with "cannot import build_prompt / CodeGenerator"

- [ ] **Step 3: Write minimal implementation**

Append to `tests/analyze_yield/code_generator.py`:

```python
import subprocess

CLAUDE_SYSTEM_PROMPT = """你是一个精密的自动化数据分析助手。

用户会提供:
1. 一个 Excel 文件的绝对路径
2. 该文件的表头结构和前几行数据抽样 (schema)
3. 用户对该文件的具体查询/分析需求

请根据表头结构，编写一段使用 pandas 的 Python3 代码来完美实现用户的查询需求。

【严格限制要求】：
1. 输出必须是能够直接运行的纯 Python 代码，读取文件时请直接使用用户提供的绝对路径。
2. 绝对不能包含任何 Markdown 语法（如 ```python 标记）、不能包含任何前后解释性文字。
3. 代码最后必须使用 print() 把计算结果以清晰易读的格式打印出来。
4. 如果查询结果是一个 DataFrame，请使用 print(df.to_string()) 打印。
5. 不要使用 plt.show() 或任何需要 GUI 的绘图命令。如需绘图请用 print() 输出数据。
6. 仅使用 pandas 和 Python 标准库，不要导入未安装的第三方库。
"""


def build_prompt(schema: str, user_demand: str, file_path: str) -> str:
    """构建发送给 Claude CLI 的完整 prompt。

    Args:
        schema: Excel 文件的表头和抽样数据
        user_demand: 用户的自然语言查询需求
        file_path: 目标 Excel 文件的绝对路径

    Returns:
        完整的 prompt 字符串
    """
    return (
        f"当前环境的绝对工作目录 (Current Working Directory) 是: '{Path.cwd()}'。\n"
        f"目标 Excel 文件的【绝对路径】为: '{file_path}'。\n\n"
        f"该 Excel 文件的表头结构和前几行数据抽样如下:\n{schema}\n\n"
        f"用户当前对这个文件的具体查询/分析需求是: '{user_demand}'。\n\n"
        "请根据表头结构，编写一段使用 pandas 的 Python3 代码来完美实现用户的这个计算需求。"
    )


class CodeGenerator:
    """通过 Claude CLI 驱动 pandas 代码生成的生成器。

    使用 subprocess 调用 claude -p 进行非交互式代码生成。
    Claude 的代码生成质量优于普通 LLM API 调用。
    """

    def __init__(self, claude_bin: str = "claude") -> None:
        self._claude_bin = claude_bin

    def generate_code(
        self,
        schema: str,
        user_demand: str,
        file_path: str,
    ) -> str:
        """生成 pandas 数据分析代码。

        Args:
            schema: Excel 文件的表头和抽样数据
            user_demand: 用户的自然语言查询需求
            file_path: 目标 Excel 文件的绝对路径

        Returns:
            清理后的纯 Python 代码字符串

        Raises:
            RuntimeError: Claude CLI 返回空代码或非零退出码
        """
        user_prompt = build_prompt(schema, user_demand, file_path)
        full_prompt = CLAUDE_SYSTEM_PROMPT + "\n\n" + user_prompt

        proc = subprocess.run(
            [self._claude_bin, "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if proc.returncode != 0:
            raise RuntimeError(
                f"Claude CLI 返回非零退出码 {proc.returncode}: {proc.stderr}"
            )

        cleaned = self._clean_code(proc.stdout)
        if not cleaned.strip():
            raise RuntimeError("Claude CLI 返回了空代码")
        return cleaned

    @staticmethod
    def _clean_code(text: str) -> str:
        """清理 Claude 响应中的 Markdown 标记和前后空白。"""
        text = text.strip()
        if text.startswith("```"):
            first_nl = text.find("\n")
            if first_nl != -1:
                text = text[first_nl + 1:]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_code_generator.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/analyze_yield/code_generator.py tests/unit/test_code_generator.py
git commit -m "feat: add CodeGenerator with prompt building and LLM code generation"
```

---

### Task 4: Code Executor — Safe Execution

**Files:**
- Create: `tests/analyze_yield/code_executor.py`
- Test: `tests/unit/test_code_executor.py`

- [ ] **Step 1: Write the failing test for `CodeExecutor`**

```python
"""test_code_executor.py - CodeExecutor 单元测试"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.analyze_yield.code_executor import CodeExecutor, ExecutionResult


class TestExecutionResult:
    """测试 ExecutionResult 数据类。"""

    def test_execution_result_success(self):
        result = ExecutionResult(
            success=True,
            stdout="col1\n0  1",
            dataframes=[pd.DataFrame({"col1": [1]})],
        )
        assert result.success
        assert "col1" in result.stdout
        assert len(result.dataframes) == 1

    def test_execution_result_failure(self):
        result = ExecutionResult(
            success=False,
            stdout="",
            error_message="NameError: name 'foo' is not defined",
        )
        assert not result.success
        assert "NameError" in result.error_message


class TestParseStdoutToDataframes:
    """测试 stdout→DataFrame 解析。"""

    def test_parse_table_output(self):
        """解析 print(df.to_string()) 格式的输出为 DataFrame。"""
        stdout = (
            "   日期       良率  型号\n"
            "0  2026-05-01  0.95  3TED01\n"
            "1  2026-05-02  0.96  3TED02"
        )
        dfs = CodeExecutor._parse_stdout_to_dataframes(stdout)
        assert len(dfs) >= 1
        df = dfs[0]
        assert list(df.columns) == ["日期", "良率", "型号"]
        assert df["良率"].iloc[0] == 0.95

    def test_parse_empty_output(self):
        """空输出返回空列表。"""
        dfs = CodeExecutor._parse_stdout_to_dataframes("")
        assert dfs == []

    def test_parse_non_table_output(self):
        """非表格文本返回空列表。"""
        dfs = CodeExecutor._parse_stdout_to_dataframes("A random string with no table")
        assert dfs == []


class TestCodeExecutor:
    """测试代码执行器。"""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> tuple[CodeExecutor, Path]:
        """创建测试用的 CodeExecutor 和 Excel 文件。"""
        file_path = tmp_path / "data.xlsx"
        pd.DataFrame({
            "日期": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "良率": [0.95, 0.96, 0.94],
        }).to_excel(file_path, index=False)
        return CodeExecutor(), file_path

    def test_execute_simple_code(self, executor):
        """执行简单的 print 代码应成功捕获输出。"""
        exec_, file_path = executor
        code = (
            "import pandas as pd\n"
            f"df = pd.read_excel(r'{file_path}')\n"
            "print(df['良率'].mean())"
        )
        result = exec_.execute(code)
        assert result.success
        assert "0.95" in result.stdout

    def test_execute_code_with_error(self, executor):
        """执行有语法错误的代码应返回失败。"""
        exec_, file_path = executor
        code = "print(undefined_variable)"
        result = exec_.execute(code)
        assert not result.success
        assert result.error_message != ""

    def test_execute_captures_dataframes(self, executor):
        """执行 print(df.to_string()) 应捕获输出并可解析为 DataFrame。"""
        exec_, file_path = executor
        code = (
            "import pandas as pd\n"
            f"df = pd.read_excel(r'{file_path}')\n"
            "print(df.to_string())"
        )
        result = exec_.execute(code)
        assert result.success
        assert "良率" in result.stdout
        assert len(result.dataframes) >= 1

    def test_execute_with_timeout(self, executor):
        """超时代码应被终止并返回失败。"""
        exec_, file_path = executor
        code = "import time; time.sleep(30)"
        result = exec_.execute(code, timeout=1)
        assert not result.success
        assert "timeout" in result.error_message.lower()

    def test_temp_file_cleanup(self, executor):
        """临时 .py 文件应在执行后被清理。"""
        import tempfile
        exec_, file_path = executor

        # 记录执行前的临时文件
        before = set(Path(tempfile.gettempdir()).glob("analyze_yield_*.py"))
        result = exec_.execute("print('hello')")
        after = set(Path(tempfile.gettempdir()).glob("analyze_yield_*.py"))

        assert result.success
        # 执行后不应留下新的临时文件
        assert before == after
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_code_executor.py -v`
Expected: FAIL with "cannot import CodeExecutor"

- [ ] **Step 3: Write minimal implementation**

```python
"""code_executor.py - 安全的 Python 代码执行器

通过将 LLM 生成的代码写入临时 .py 文件，
再使用 subprocess.run 启动独立 Python 进程执行，
实现操作系统级别的 stdout/stderr 完整捕获。
Windows/Linux 跨平台兼容。
"""

from __future__ import annotations

import io
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """代码执行结果。

    Attributes:
        success: 是否执行成功
        stdout: 捕获的标准输出
        dataframes: 从 stdout 解析出的 DataFrame 列表，供 st.dataframe() 渲染
        error_message: 失败时的错误信息
    """

    success: bool
    stdout: str = ""
    dataframes: list[pd.DataFrame] = field(default_factory=list)
    error_message: str = ""


class CodeExecutor:
    """安全执行 LLM 生成的 pandas 代码。

    工作方式：将代码写入临时 .py 文件，
    然后 subprocess.run([python, tmp.py])，
    通过操作系统级别的 capture_output=True 捕获所有输出。
    执行完毕后自动清理临时文件。
    """

    def __init__(self) -> None:
        pass

    def execute(self, code: str, timeout: int = 30) -> ExecutionResult:
        """执行一段 Python 代码并捕获输出。

        Args:
            code: 要执行的 Python 代码字符串
            timeout: 最大执行时间（秒）

        Returns:
            ExecutionResult 包含 stdout、解析后的 DataFrame 列表和错误信息
        """
        tmp_path = None
        try:
            # 写入临时 .py 文件 (delete=False 以便 subprocess 读取后手动清理)
            fd, tmp_path_str = tempfile.mkstemp(
                suffix=".py", prefix="analyze_yield_"
            )
            os.close(fd)
            tmp_path = Path(tmp_path_str)
            tmp_path.write_text(code, encoding="utf-8")

            proc = subprocess.run(
                [sys.executable, str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            self._cleanup(tmp_path)
            return ExecutionResult(
                success=False,
                stdout="",
                error_message=f"代码执行超时（>{timeout}秒），已被终止。",
            )
        finally:
            self._cleanup(tmp_path)

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        if proc.returncode != 0:
            combined = stdout
            if stderr:
                combined += "\n" + stderr
            return ExecutionResult(
                success=False,
                stdout=stdout,
                error_message=combined.strip() or "代码执行返回非零退出码",
            )

        dataframes = self._parse_stdout_to_dataframes(stdout)
        return ExecutionResult(success=True, stdout=stdout, dataframes=dataframes)

    @staticmethod
    def _parse_stdout_to_dataframes(stdout: str) -> list[pd.DataFrame]:
        """尝试将 stdout 文本解析为 DataFrame 列表。

        解析策略:
        1. 尝试用 pd.read_csv(StringIO(stdout), sep=r'\s+') 解析整个输出
        2. 如果失败，返回空列表（前端降级为 st.code 渲染）

        Args:
            stdout: 代码执行的标准输出文本

        Returns:
            解析出的 DataFrame 列表
        """
        if not stdout.strip():
            return []
        try:
            df = pd.read_csv(io.StringIO(stdout), sep=r"\s+")
            if len(df.columns) > 0 and len(df) > 0:
                return [df]
        except Exception:
            pass
        return []

    @staticmethod
    def _cleanup(tmp_path: Path | None) -> None:
        """清理临时文件。"""
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_code_executor.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/analyze_yield/code_executor.py tests/unit/test_code_executor.py
git commit -m "feat: add CodeExecutor for safe code execution"
```

---

### Task 5: Streamlit UI — Tab 4 智能查询

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add Tab 4 after Tab 3 in `app/main.py`**

In `app/main.py`, modify the tab definition at line 162 from:

```python
tab1, tab2, tab3 = st.tabs(
    ["📥 报表下载", "📤 数据上传与分析", "📥 报告下载"]
)
```

to:

```python
tab1, tab2, tab3, tab4 = st.tabs(
    ["📥 报表下载", "📤 数据上传与分析", "📥 报告下载", "💬 智能查询"]
)
```

- [ ] **Step 2: Add session state and disk persistence for Tab 4**

First, add `import json` to the existing imports at the top of the file (after line 38 `from pathlib import Path`). Then, after line 116 (`st.session_state.last_query_result = None`), add:

```python
QUERY_HISTORY_FILE = Path("docs/query_history.json")

def _load_query_history() -> list[dict]:
    """从磁盘加载查询历史。"""
    if QUERY_HISTORY_FILE.exists():
        try:
            return json.loads(QUERY_HISTORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []

def _save_query_history(history: list[dict]) -> None:
    """保存查询历史到磁盘。"""
    QUERY_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUERY_HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

if "smart_query_history" not in st.session_state:
    st.session_state.smart_query_history = _load_query_history()
```

- [ ] **Step 3: Add Tab 4 UI code after Tab 3's `with tab3:` block**

After the closing of `with tab3:` (before the page footer at line 513), add:

```python
# ============================================================
# Tab 4: 智能查询
# ============================================================
with tab4:
    from pathlib import Path
    from tests.analyze_yield.code_generator import CodeGenerator, extract_schema
    from tests.analyze_yield.code_executor import CodeExecutor

    st.markdown("### 💬 智能查询")
    st.caption(
        "输入自然语言查询需求，Claude 自动生成 pandas 代码对 Excel 文件进行分析。"
    )

    # ---- 文件选择区 ----
    st.markdown("#### 📂 选择数据文件")
    project_files_dir = Path("docs/project_files")
    if project_files_dir.exists():
        available_files = sorted(
            [f for f in project_files_dir.iterdir()
             if f.is_file() and f.suffix in (".xlsx", ".xls")],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        file_options = {f.name: f for f in available_files}
        selected_filename = st.selectbox(
            "选择要查询的 Excel 文件",
            options=list(file_options.keys()),
            help="列出 docs/project_files/ 下的所有 Excel 文件",
        )
        selected_file = file_options[selected_filename]

        # 显示 Schema 预览
        with st.expander("📋 文件 Schema 预览", expanded=False):
            try:
                schema = extract_schema(selected_file)
                st.code(schema, language="text")
            except Exception as e:
                st.warning(f"无法读取文件 schema: {e}")
    else:
        st.warning("docs/project_files/ 目录不存在。")
        selected_file = None

    # ---- 查询输入区 ----
    st.markdown("#### ✏️ 输入查询需求")

    with st.expander("💡 查询示例（点击展开）", expanded=False):
        st.markdown("""
        | 查询目的 | 示例语句 |
        |----------|----------|
        | 基本统计 | "统计良率的平均值、最大值和最小值" |
        | 筛选查询 | "搜出5月良率低于95%的数据" |
        | 分组聚合 | "按产品型号分组，计算各型号平均良率" |
        | 趋势分析 | "按日期排序，展示良率变化趋势" |
        """)

    # 代码预览 toggle
    preview_only = st.toggle(
        "🔍 仅生成代码，不执行",
        value=False,
        help="开启后只展示 Claude 生成的 pandas 代码，不会在本地执行。"
    )

    col_input, col_btn = st.columns([5, 1])
    with col_input:
        user_demand = st.text_input(
            "自然语言查询",
            placeholder="例如: 统计5月各型号良率的平均值和标准差",
            label_visibility="collapsed",
            key="smart_query_input",
        )
    with col_btn:
        btn_label = "🧠 生成代码" if preview_only else "🚀 执行查询"
        execute_btn = st.button(btn_label, type="primary", use_container_width=True)

    # ---- 执行查询 ----
    if execute_btn and user_demand and selected_file:
        with st.chat_message("user"):
            st.markdown(user_demand)

        try:
            # Step 1: 提取 schema
            with st.spinner("正在分析文件结构..."):
                schema = extract_schema(selected_file)
                abs_path = str(selected_file.resolve())

            # Step 2: Claude CLI 生成代码
            with st.spinner("Claude 正在生成分析代码..."):
                generator = CodeGenerator(claude_bin="claude")
                generated_code = generator.generate_code(schema, user_demand, abs_path)

            # Step 3: 显示生成的代码（始终展示）
            with st.expander("🔍 查看生成的代码", expanded=True):
                st.code(generated_code, language="python")

            if preview_only:
                st.info("代码预览模式 — 未执行。如需执行，请关闭上方 toggle 后重新点击按钮。")
                # 仅预览也记录历史
                st.session_state.smart_query_history.append({
                    "query": user_demand,
                    "file": selected_file.name,
                    "success": True,
                    "preview_only": True,
                    "code": generated_code,
                })
                _save_query_history(st.session_state.smart_query_history)
            else:
                # Step 4: 执行代码
                with st.spinner("正在执行分析..."):
                    executor = CodeExecutor()
                    result = executor.execute(generated_code)

                # Step 5: 显示结果
                st.divider()
                st.markdown("#### 📊 查询结果")

                if result.success:
                    if result.dataframes:
                        for i, df in enumerate(result.dataframes):
                            st.dataframe(df, use_container_width=True)
                    else:
                        st.code(result.stdout, language="text")
                else:
                    st.error(f"代码执行失败:\n```\n{result.error_message}\n```")
                    if result.stdout:
                        st.markdown("**部分输出:**")
                        st.code(result.stdout, language="text")

                # 记录查询历史并持久化
                st.session_state.smart_query_history.append({
                    "query": user_demand,
                    "file": selected_file.name,
                    "success": result.success,
                    "preview_only": False,
                    "error": result.error_message if not result.success else "",
                })
                _save_query_history(st.session_state.smart_query_history)

        except RuntimeError as e:
            st.error(f"Claude 代码生成失败: {e}")
        except Exception as e:
            st.error(f"查询执行失败: {e}")

    elif execute_btn and not user_demand:
        st.warning("请输入查询语句。")
    elif execute_btn and not selected_file:
        st.warning("请选择要查询的文件。")

    # ---- 查询历史 ----
    if st.session_state.smart_query_history:
        st.divider()
        st.markdown("#### 📜 查询历史")
        for i, entry in enumerate(reversed(st.session_state.smart_query_history[-10:])):
            with st.container():
                if entry.get("preview_only"):
                    status = "🔍"
                else:
                    status = "✅" if entry["success"] else "❌"
                st.markdown(
                    f"{status} **{entry['file']}** — {entry['query']}"
                )
```

- [ ] **Step 4: Verify the app launches without import errors**

Run: `uv run python -c "from tests.analyze_yield.code_generator import CodeGenerator, extract_schema; from tests.analyze_yield.code_executor import CodeExecutor; print('Import OK')"`
Expected: `Import OK`

- [ ] **Step 5: Run all tests to verify no regressions**

Run: `uv run pytest tests/ -v --tb=short`
Expected: all tests PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
git add app/main.py
git commit -m "feat: add Tab 4 smart query with LLM-powered Excel analysis"
```

---

### Task 6: Remove Obsolete Shell Script

**Files:**
- Delete: `tests/analyze_yield.sh`

- [ ] **Step 1: Delete the old shell script**

```bash
git rm tests/analyze_yield.sh
```

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: remove obsolete analyze_yield.sh, replaced by smart query module"
```
