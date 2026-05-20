"""code_generator.py - LLM 驱动的 pandas 代码生成器"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def _looks_like_data(value) -> bool:
    """判断一个值是否更可能为数据而非表头名。

    返回 True 如果值看起来像:
    - 数字（int/float）
    - 日期字符串 (YYYY-MM-DD / YYYY/MM/DD)
    - 纯数字字符串 (如 "001", "2026")
    - 其他明显的非表头模式
    """
    if isinstance(value, (int, float)):
        return True
    if not isinstance(value, str):
        return False
    # 尝试转数字
    try:
        float(value)
        return True
    except ValueError:
        pass
    # 日期格式检测
    import re
    if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", value):
        return True
    # 纯数字字符串 (如产品编号 "001")
    if re.match(r"^\d+(\.\d+)?$", value):
        return True
    # 百分比字符串 (如 "95.0%")
    if re.match(r"^\d+(\.\d+)?%$", value):
        return True
    return False


def _is_header_row(row: pd.Series) -> bool:
    """判断一行是否为表头行（非数据文本占多数）。

    逻辑：如果一行中大部分非空值都不像典型数据（数字/日期等），
    则该行很可能是一个描述性的表头行。
    """
    non_null = row.dropna()
    if len(non_null) == 0:
        return False
    data_like_count = sum(1 for v in non_null if _looks_like_data(v))
    # 如果像数据的值不足一半，则认为是表头行
    return data_like_count < len(non_null) * 0.5


def _is_merged_title_row(row: pd.Series, threshold: float = 0.7) -> bool:
    """判断一行是否为合并单元格产生的标题/元数据行。

    特征：ffill 后该行的绝大多数列包含相同文本（如报告标题）。

    Args:
        row: DataFrame 的一行
        threshold: 判定为标题行的最低重复比例

    Returns:
        True 如果该行应被排除（标题/元数据），不应参与表头或数据
    """
    non_null = row.dropna()
    if len(non_null) == 0:
        return True
    # 统计出现最多的值的占比
    value_counts = non_null.value_counts()
    if len(value_counts) == 0:
        return True
    top_ratio = value_counts.iloc[0] / len(non_null)
    return top_ratio >= threshold


def _detect_header_depth(df: pd.DataFrame, max_scan: int = 5) -> int:
    """检测多级表头深度。

    从第 0 行开始向下扫描，直到某行不再符合表头特征。
    至少保留 1 行作为列名。

    Returns:
        表头行数（至少 1）
    """
    depth = 0
    for i in range(min(max_scan, len(df))):
        if _is_header_row(df.iloc[i]):
            depth += 1
        else:
            break
    return max(depth, 1)


def _flatten_multi_header(df: pd.DataFrame, header_rows: int) -> list[str]:
    """将多级表头扁平化为单级列名。

    对每一列，从上到下拼接各级表头文本（跳过 NaN/空字符串），
    用 '|' 分隔不同层级。

    Args:
        df: 包含表头行的 DataFrame（header=None 读取的）
        header_rows: 表头占用的行数

    Returns:
        扁平化后的列名列表
    """
    header_df = df.iloc[:header_rows]
    columns: list[str] = []
    for col_idx in range(len(df.columns)):
        parts: list[str] = []
        for row_idx in range(len(header_df)):
            val = header_df.iloc[row_idx, col_idx]
            if pd.notna(val) and str(val).strip():
                parts.append(str(val).strip())
        columns.append(" | ".join(parts) if parts else f"列{col_idx}")
    return columns


def _build_markdown_table(df: pd.DataFrame, max_data_rows: int = 5) -> str:
    """将 DataFrame 的前 N 行数据构建为 Markdown 表格。

    手动构建 pipe table，避免依赖 tabulate 包。
    """
    cols = list(df.columns)
    data_rows = df.head(max_data_rows)

    lines: list[str] = []
    # 表头
    lines.append("| " + " | ".join(str(c) for c in cols) + " |")
    # 分隔行
    lines.append("| " + " | ".join("---" for _ in cols) + " |")
    # 数据行
    for _, row in data_rows.iterrows():
        cells = [str(v) if pd.notna(v) else "" for v in row]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def extract_schema(file_path: Path, nrows: int = 20) -> str:
    """从 Excel 文件提取高保真 Schema 结构描述。

    处理流程:
    1. 读取前 N 行（默认 20），header=None 保留原始行结构
    2. 前向填充修复合并单元格塌陷产生的 NaN
    3. 智能检测多级表头并扁平化
    4. 输出结构化 Markdown Schema 描述

    Args:
        file_path: Excel 文件路径
        nrows: 读取的数据行数（包含表头）

    Returns:
        结构化的 Markdown Schema 描述文本

    Raises:
        FileNotFoundError: 文件不存在
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # Step 1: 原始读取（header=None 避免 pandas 自动解析表头）
    df = pd.read_excel(file_path, nrows=nrows, header=None)

    # Step 1.5: 删除全空列
    df = df.dropna(axis=1, how="all")

    # Step 2: 双向前向填充 — 修复合并单元格塌陷产生的 NaN
    df = df.ffill(axis=0).ffill(axis=1)

    # Step 2.5: 排除合并标题行（ffill 后大多数列内容相同的行）
    title_mask = df.apply(_is_merged_title_row, axis=1)
    non_title_indices = df.index[~title_mask]
    if len(non_title_indices) == 0:
        # 所有行都是标题行，退化为原始处理
        non_title_indices = df.index
    working_df = df.loc[non_title_indices].reset_index(drop=True)

    # Step 3: 检测多级表头深度（基于排除了标题行的工作副本）
    header_depth = _detect_header_depth(working_df)

    # Step 4: 扁平化表头 + 截取数据区
    if header_depth > 1:
        flat_columns = _flatten_multi_header(working_df, header_depth)
    else:
        flat_columns = [str(v) if pd.notna(v) else f"列{i}"
                        for i, v in enumerate(working_df.iloc[0])]

    data_df = working_df.iloc[header_depth:].reset_index(drop=True)
    data_df.columns = flat_columns

    # 尝试将各列转换为数值类型以获得更准确的 dtype（Pandas 3.x compatible）
    for col in data_df.columns:
        try:
            data_df[col] = pd.to_numeric(data_df[col])
        except (ValueError, TypeError):
            pass  # 非数值列保持原样

    # Step 5: 推断各列 dtype 和典型值
    dtype_info: list[dict] = []
    for col in data_df.columns:
        series = data_df[col].dropna()
        if len(series) == 0:
            dtype_info.append({"col": col, "dtype": "unknown", "samples": ""})
            continue
        dtype_name = str(series.dtype) if hasattr(series, "dtype") else "object"
        # 如果是 object 但可以转数字，标注为 mixed
        samples = ", ".join(str(v) for v in list(series.head(3)))
        dtype_info.append({"col": col, "dtype": dtype_name, "samples": samples})

    # Step 6: 构建结构化 Markdown 输出
    md_lines: list[str] = []
    md_lines.append("【数据表元数据与高保真 Schema 结构】")
    md_lines.append(f"- 有效列数: {len(data_df.columns)}")
    md_lines.append(f"- 有效数据行数（抽样）: {len(data_df)}")
    md_lines.append("- 结构清洗说明: 已通过前向填充算法自动修复合并单元格产生的 NaN 塌陷。")
    md_lines.append("")
    md_lines.append("【字段与数据抽样 (已对齐修复)】")
    md_lines.append("| 列名 | 数据类型 | 典型有效值示例 |")
    md_lines.append("| --- | --- | --- |")
    for info in dtype_info:
        md_lines.append(f"| {info['col']} | {info['dtype']} | {info['samples']} |")
    md_lines.append("")
    md_lines.append(f"【前 {min(5, len(data_df))} 行纯净数据快照】")
    md_lines.append(_build_markdown_table(data_df, max_data_rows=5))

    return "\n".join(md_lines)


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
        "\n代码约束：只输出纯 Python 代码，禁止 Markdown 标记，最后必须用 print() 打印结果。"
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
