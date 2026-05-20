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
    return df.to_string(index=False)
