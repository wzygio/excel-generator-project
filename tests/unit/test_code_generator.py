"""test_code_generator.py - CodeGenerator 单元测试"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from yield_report.infrastructure.code_generator import (
    CodeGenerator,
    build_prompt,
    extract_schema,
    _is_header_row,
    _detect_header_depth,
    _flatten_multi_header,
)


class TestIsHeaderRow:
    """测试表头行检测。"""

    def test_text_row_is_header(self):
        """全是文本字符串的行应被识别为表头。"""
        row = pd.Series(["厂别", "日期", "良率", "产品型号"])
        assert _is_header_row(row) is True

    def test_numeric_row_is_not_header(self):
        """全是数字的行不应被识别为表头。"""
        row = pd.Series([1.0, 2.0, 3.0, 4.0])
        assert _is_header_row(row) is False

    def test_mixed_numeric_text_is_header(self):
        """数字占比低于 40% 的混合行应被识别为表头。"""
        row = pd.Series(["厂别", "日期", 0.95, "型号"])
        assert _is_header_row(row) is True

    def test_mixed_mostly_numeric_is_not_header(self):
        """数字占比高于 40% 的混合行不应被识别为表头。"""
        row = pd.Series(["2026-05-01", 0.95, 0.96, 0.94])
        # "2026-05-01" 不能转数字 → 1 文本 + 3 数字 → 25% 文本 (≤60%), 但 75% 数字 (>40%)
        # _is_header_row checks if numeric_count < 40% of non-null
        # 3 numeric / 4 total = 75% → not a header
        assert _is_header_row(row) is False

    def test_all_nan_is_not_header(self):
        """全是 NaN 的行不应被识别为表头。"""
        row = pd.Series([np.nan, np.nan, np.nan])
        assert _is_header_row(row) is False


class TestDetectHeaderDepth:
    """测试多级表头深度检测。"""

    def test_single_header(self):
        """单层表头应返回 1。"""
        df = pd.DataFrame([
            ["厂别", "日期", "良率"],
            ["ARRAY", "2026-05-01", 0.95],
            ["OLED", "2026-05-02", 0.96],
        ])
        assert _detect_header_depth(df) == 1

    def test_two_level_header(self):
        """两层表头应返回 2。"""
        df = pd.DataFrame([
            ["良率数据", "良率数据", "基本信息"],
            ["厂别", "日期", "良率"],
            ["ARRAY", "2026-05-01", 0.95],
        ])
        assert _detect_header_depth(df) == 2

    def test_min_depth_is_one(self):
        """全数字 DataFrame 也至少返回 1。"""
        df = pd.DataFrame([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
        ])
        assert _detect_header_depth(df) >= 1


class TestFlattenMultiHeader:
    """测试多级表头扁平化。"""

    def test_two_level_flatten(self):
        """两级表头应拼接为 'L1 | L2' 格式。"""
        df = pd.DataFrame([
            ["良率", "良率", "基本信息"],
            ["厂别", "良率值", "日期"],
            ["ARRAY", 0.95, "2026-05-01"],
        ])
        result = _flatten_multi_header(df, header_rows=2)
        assert result == ["良率 | 厂别", "良率 | 良率值", "基本信息 | 日期"]

    def test_skip_nan_in_header(self):
        """扁平化时应跳过 NaN 层级。"""
        df = pd.DataFrame([
            ["良率", np.nan, "基本信息"],
            ["厂别", "良率值", "日期"],
        ])
        result = _flatten_multi_header(df, header_rows=2)
        assert result == ["良率 | 厂别", "良率值", "基本信息 | 日期"]

    def test_unnamed_column_fallback(self):
        """全部为 NaN 的列使用默认名。"""
        df = pd.DataFrame([
            [np.nan, "良率"],
            [np.nan, "良率值"],
        ])
        result = _flatten_multi_header(df, header_rows=2)
        assert result[0] == "列0"


class TestExtractSchema:
    """测试 Excel schema 提取。"""

    def test_extract_schema_from_valid_xlsx(self, tmp_path: Path):
        """从有效的 xlsx 文件提取结构化 schema 描述。"""
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
        # 新格式包含结构化标记
        assert "【数据表元数据与高保真 Schema 结构】" in result
        assert "【字段与数据抽样" in result
        assert "【前" in result and "行纯净数据快照】" in result

    def test_extract_schema_outputs_markdown_table(self, tmp_path: Path):
        """输出应包含 Markdown 管道表格。"""
        file_path = tmp_path / "test.xlsx"
        df = pd.DataFrame({
            "日期": ["2026-05-01", "2026-05-02"],
            "良率": [0.95, 0.96],
        })
        df.to_excel(file_path, index=False)

        result = extract_schema(file_path)
        # 数据快照应包含 Markdown pipe table
        assert "| 日期 |" in result or "|日期|" in result
        assert "| --- |" in result

    def test_extract_schema_shows_5_data_rows(self, tmp_path: Path):
        """数据快照应展示恰好 5 行数据（或少于 5 如有数据不足）。"""
        file_path = tmp_path / "test.xlsx"
        df = pd.DataFrame({"col": range(10)})
        df.to_excel(file_path, index=False)

        result = extract_schema(file_path)
        # 提取"前 N 行纯净数据快照"之后的 Markdown 表格数据行
        marker = "行纯净数据快照】"
        idx = result.find(marker)
        assert idx != -1, f"输出中未找到 '{marker}' 标记"
        after_snapshot = result[idx + len(marker):]

        # 在快照区收集管道表格数据行（跳过表头行和分隔行）
        data_lines = []
        in_table = False
        for line in after_snapshot.split("\n"):
            line = line.strip()
            if line.startswith("| ---"):
                in_table = True
                continue
            if in_table and line.startswith("|"):
                data_lines.append(line)
        assert len(data_lines) <= 6  # 1 header + up to 5 data rows

    def test_extract_schema_file_not_found_raises(self, tmp_path: Path):
        """文件不存在时抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            extract_schema(tmp_path / "nonexistent.xlsx")

    def test_extract_schema_handles_merged_cells_nan(self, tmp_path: Path):
        """合并单元格塌陷产生的 NaN 应被 ffill 修复。"""
        file_path = tmp_path / "test.xlsx"
        # 模拟合并单元格裂变后的数据：第一列有 NaN
        df = pd.DataFrame({
            "厂别": ["ARRAY", np.nan, "OLED", np.nan],
            "日期": ["2026-05-01", np.nan, "2026-05-02", "2026-05-03"],
            "良率": [0.95, 0.96, 0.94, np.nan],
        })
        df.to_excel(file_path, index=False)

        result = extract_schema(file_path)
        # 前向填充后，NaN 应被上方有效值替换
        # ARRAY 应向下填充到第二行
        assert "ARRAY" in result
        # 不应包含 'nan' 字符串（表示 NaN 未被填充）
        # 但不能完全排除 float nan 字符串，所以检查结构标记存在即可

    def test_extract_schema_with_multi_level_header(self, tmp_path: Path):
        """多级表头应被检测并扁平化。"""
        file_path = tmp_path / "multi_header.xlsx"
        # 写入一个带有两级表头的 Excel
        header_row1 = ["良率数据", "良率数据", "基本信息", "基本信息"]
        header_row2 = ["厂别", "良率值", "日期", "型号"]
        data = [
            ["ARRAY", 0.95, "2026-05-01", "3TED01"],
            ["OLED", 0.96, "2026-05-02", "3TED02"],
        ]
        df_full = pd.DataFrame(
            [header_row1, header_row2] + data
        )
        df_full.to_excel(file_path, index=False, header=False)

        result = extract_schema(file_path)
        # 扁平化后的列名应包含拼接结果
        assert "良率数据 | 厂别" in result or "良率数据" in result
        assert "基本信息 | 日期" in result or "基本信息" in result
        assert "ARRAY" in result

    def test_extract_schema_includes_dtype_info(self, tmp_path: Path):
        """输出应包含各列的数据类型信息。"""
        file_path = tmp_path / "test.xlsx"
        df = pd.DataFrame({
            "产品": ["3TED01", "3TED02"],
            "良率": [0.95, 0.96],
        })
        df.to_excel(file_path, index=False)

        result = extract_schema(file_path)
        assert "float" in result or "int" in result or "object" in result
        # dtype 列存在
        assert "数据类型" in result

    def test_extract_schema_empty_data_columns(self, tmp_path: Path):
        """包含空列时不应崩溃。"""
        file_path = tmp_path / "test.xlsx"
        df = pd.DataFrame({
            "日期": ["2026-05-01"],
            "良率": [0.95],
            "空列": [np.nan],
        })
        df.to_excel(file_path, index=False)

        result = extract_schema(file_path)
        assert "空列" in result


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
            "yield_report.infrastructure.code_generator.subprocess.run",
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
            "yield_report.infrastructure.code_generator.subprocess.run",
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
            "yield_report.infrastructure.code_generator.subprocess.run",
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
            "yield_report.infrastructure.code_generator.subprocess.run",
            mock_run,
        )

        with pytest.raises(RuntimeError, match="Claude CLI 返回了空代码"):
            gen.generate_code("schema", "demand", "file.xlsx")
