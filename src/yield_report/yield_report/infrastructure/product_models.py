"""
product_models.py: 产品型号列表提取工具

从 spotfire.xlsx 文件中提取产品型号列表，用于 FineReport 报表筛选。

根据 yield_report_domain.md 中的设计:
- 数据来源: resources/project_files/spotfire.xlsx
- 提取位置: Sheet1, 第一列
- 用途: 作为"V3良率及不良率By月周天汇总报表"
  和"V3良率及不良率By批次汇总报表"的"产品型号"筛选参数

加密兼容性:
  spotfire.xlsx 受企业加密软件保护，openpyxl/pandas 无法直接读取。
  本模块使用 Windows COM (Excel.Application) 透明解密读取。
  Excel.Application 是企业加密软件的白名单进程。
"""

from __future__ import annotations

import logging
from pathlib import Path

from yield_report.shared_kernel.config import config as config_loader

logger = logging.getLogger(__name__)


class ProductModelExtractionError(Exception):
    """产品型号提取失败"""


def _read_encrypted_excel_column(
    file_path: Path,
    sheet_name: str = "Sheet1",
    column: str = "A",
    start_row: int = 2,
) -> list[str]:
    """
    通过 Windows COM (Excel.Application) 读取加密 Excel 文件中的列数据。

    企业加密软件对磁盘上的 .xlsx 文件进行透明加密（文件头不是 PK\x03\x04），
    只有白名单进程（Excel.exe）能透明解密。Python 解释器不在白名单中，
    因此 openpyxl / pandas 全部失败。

    该方法利用 Windows COM 接口在本地启动 Excel.Application 进程，
    由 Excel 进程打开文件（自动触发企业解密），数据通过 COM 返回给 Python。

    Args:
        file_path: Excel 文件路径
        sheet_name: 工作表名
        column: 列字母 (如 "A", "B")
        start_row: 起始行号 (1-based)

    Returns:
        list[str]: 该列从 start_row 开始的非空字符串值列表

    Raises:
        ProductModelExtractionError: 读取失败
    """
    try:
        import pythoncom
        import win32com.client
    except ImportError as e:
        raise ProductModelExtractionError(
            f"缺少 pywin32 库: {e}\n请执行: uv add pywin32 pywin32"
        ) from e

    # COM 初始化（每个线程需要独立初始化）
    pythoncom.CoInitialize()

    excel = None
    wb = None
    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        wb = excel.Workbooks.Open(str(file_path.resolve()))
        ws = wb.Worksheets(sheet_name)

        values: list[str] = []
        row = start_row
        while True:
            cell = ws.Range(f"{column}{row}")
            val = cell.Value
            if val is None:
                break
            value_str = str(val).strip()
            if value_str:
                values.append(value_str)
            row += 1

        logger.debug(
            "COM 读取 %s[%s!%s%d:] 共 %d 个值",
            file_path.name,
            sheet_name,
            column,
            start_row,
            len(values),
        )
        return values

    except Exception as e:
        raise ProductModelExtractionError(
            f"通过 COM 读取 {file_path}[{sheet_name}!{column}{start_row}] 失败: {e}"
        ) from e

    finally:
        if wb is not None:
            try:
                wb.Close(SaveChanges=False)
            except Exception:
                pass
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def extract_product_models(
    spotfire_path: str | Path | None = None,
) -> list[str]:
    """
    从 spotfire.xlsx 中提取产品型号列表。

    读取逻辑:
    1. 通过 Windows COM (Excel.Application) 打开加密文件
    2. 读取 Sheet1 第一列 (A列) 第2行开始
    3. 遇到空单元格停止
    4. 每个单元格的字符串值作为一个产品型号

    Args:
        spotfire_path: spotfire.xlsx 文件路径，默认为
                       resources/project_files/spotfire.xlsx

    Returns:
        list[str]: 产品型号列表 (例如 ["3TED01", "3TED02", ...])

    Raises:
        ProductModelExtractionError: 文件不存在或提取失败
        FileNotFoundError: 文件不存在时的后备异常
    """
    if spotfire_path is None:
        app_config = config_loader.get()
        resources_dir = Path(app_config.paths.resources_dir)
        spotfire_path = resources_dir / "project_files" / "spotfire.xlsx"

    spotfire_path = Path(spotfire_path)

    if not spotfire_path.exists():
        raise FileNotFoundError(
            f"spotfire.xlsx 文件未找到: {spotfire_path}"
        )

    # 通过 Windows COM 读取加密文件
    models = _read_encrypted_excel_column(
        file_path=spotfire_path,
        sheet_name="Sheet1",
        column="A",
        start_row=2,
    )

    if not models:
        logger.warning("spotfire.xlsx[Sheet1] 中未提取到任何产品型号")
    else:
        logger.info(
            "从 spotfire.xlsx 中提取到 %d 个产品型号: %s ...",
            len(models),
            models[:5],
        )

    return models
