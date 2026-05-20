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
