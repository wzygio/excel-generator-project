"""test_code_generator.py - CodeGenerator 单元测试"""

from __future__ import annotations

import subprocess
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
        assert len(lines) == 6

    def test_extract_schema_file_not_found_raises(self, tmp_path: Path):
        """文件不存在时抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            extract_schema(tmp_path / "nonexistent.xlsx")


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
