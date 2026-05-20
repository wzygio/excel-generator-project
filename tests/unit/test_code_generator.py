"""test_code_generator.py - CodeGenerator 单元测试"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.analyze_yield.code_generator import extract_schema


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
