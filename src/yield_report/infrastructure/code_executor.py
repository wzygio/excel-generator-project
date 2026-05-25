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
                error_message=f"timeout: 代码执行超时（>{timeout}秒），已被终止。",
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
        r"""尝试将 stdout 文本解析为 DataFrame 列表。

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
