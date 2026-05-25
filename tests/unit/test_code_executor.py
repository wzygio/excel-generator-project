"""test_code_executor.py - CodeExecutor 单元测试"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from yield_report.infrastructure.code_executor import CodeExecutor, ExecutionResult


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
        # Floating-point: mean of [0.95, 0.96, 0.94] may be 0.949999...
        float_val = float(result.stdout.strip())
        assert abs(float_val - 0.95) < 1e-6

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
