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


# =====================================================================
# 加密文件支持
# =====================================================================

# 标准 xlsx ZIP 文件头
_PK_ZIP_HEADER = b"PK\x03\x04"
# 企业加密软件加密后的文件头特征（全零开头）
_ENCRYPTED_MAGIC_PREFIX = b"\x00\x00\x00\x00"


def _is_encrypted(file_path: Path) -> bool:
    """通过文件头魔数检测文件是否被企业加密软件加密。

    加密文件头不是 PK 开头，而是加密软件的魔数（全零或其他）。
    """
    with open(file_path, "rb") as f:
        magic = f.read(4)
    return magic != _PK_ZIP_HEADER


def _detect_sheet_name_via_com(file_path: Path, target_hint: str | None = None) -> str:
    """通过 COM 读取第一个可用 sheet 的名称（用于加密文件）。

    Args:
        file_path: Excel 文件路径
        target_hint: 可选的目标 sheet 名称提示

    Returns:
        第一个非隐藏 sheet 的名称，或 target_hint，或 "Sheet1"
    """
    if target_hint:
        return target_hint
    try:
        import win32com.client  # type: ignore[import-untyped]

        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(str(file_path))
        name = str(wb.Sheets(1).Name)
        wb.Close(SaveChanges=False)
        excel.Quit()
        return name
    except Exception:
        return "CT"  # 默认回退


def _extract_schema_via_com(file_path: Path, sheet_name: str, nrows: int = 20) -> str:
    """通过 COM 从加密 Excel 中读取数据并提取 schema（动态回退方案）。

    当静态 Schema 不存在时使用此方案。
    注意：COM 方式速度较慢（需启动 Excel 进程），仅作回退。

    Args:
        file_path: Excel 文件路径
        sheet_name: 目标 sheet 名称
        nrows: 读取行数

    Returns:
        Markdown 格式的 Schema 描述
    """
    try:
        import win32com.client  # type: ignore[import-untyped]

        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(str(file_path))
        ws = wb.Sheets(sheet_name)

        max_row = ws.UsedRange.Rows.Count
        max_col = ws.UsedRange.Columns.Count
        read_rows = min(nrows, max_row)

        # 读取数据到二维列表
        data: list[list] = []
        for row_idx in range(1, read_rows + 1):
            row_data: list = []
            for col_idx in range(1, max_col + 1):
                val = ws.Cells(row_idx, col_idx).Value
                row_data.append(val)
            data.append(row_data)

        wb.Close(SaveChanges=False)
        excel.Quit()

        # 转换为 DataFrame
        df = pd.DataFrame(data)

        # 删除全空列
        df = df.dropna(axis=1, how="all")

        # 后续复用现有逻辑
        title_mask = df.apply(_is_merged_title_row, axis=1)
        non_title_indices = df.index[~title_mask]
        if len(non_title_indices) == 0:
            non_title_indices = df.index
        working_df = df.loc[non_title_indices].reset_index(drop=True)

        header_depth = _detect_header_depth(working_df)
        if header_depth > 1:
            flat_columns = _flatten_multi_header(working_df, header_depth)
        else:
            flat_columns = [
                str(v) if pd.notna(v) else f"列{i}"
                for i, v in enumerate(working_df.iloc[0])
            ]

        data_df = working_df.iloc[header_depth:].reset_index(drop=True)
        data_df.columns = flat_columns

        for col in data_df.columns:
            try:
                data_df[col] = pd.to_numeric(data_df[col])
            except (ValueError, TypeError):
                pass

        md_lines: list[str] = []
        md_lines.append(f"【数据表元数据 - COM 动态提取 (Sheet: {sheet_name})】")
        md_lines.append(f"- 有效列数: {len(data_df.columns)}")
        md_lines.append(f"- 有效数据行数（抽样）: {len(data_df)}")
        md_lines.append("- 数据来源: 通过 COM Excel.Application 从加密文件动态读取")
        md_lines.append("")
        md_lines.append("【字段与数据抽样】")
        md_lines.append("| 列名 | 数据类型 | 典型有效值示例 |")
        md_lines.append("| --- | --- | --- |")
        for col in data_df.columns:
            series = data_df[col].dropna()
            dtype_name = str(series.dtype) if len(series) > 0 else "unknown"
            samples = ", ".join(str(v) for v in list(series.head(3))) if len(series) > 0 else ""
            md_lines.append(f"| {col} | {dtype_name} | {samples} |")
        md_lines.append("")
        md_lines.append(f"【前 {min(5, len(data_df))} 行纯净数据快照】")
        md_lines.append(_build_markdown_table(data_df, max_data_rows=5))

        return "\n".join(md_lines)

    except ImportError:
        logger.warning("pywin32 未安装，无法通过 COM 读取加密文件")
        return _build_encrypted_hint(file_path)


def _build_encrypted_hint(file_path: Path) -> str:
    """当无法读取加密文件时，返回一个提示性的 Schema 描述。"""
    return (
        f"【加密文件提示】\n"
        f"- 文件: {file_path.name}\n"
        f"- 状态: 企业加密软件保护，无法自动读取\n"
        f"- 建议: 在 Excel 中手动打开后查看结构，或在代码中通过 COM 方式读取\n"
    )


# =====================================================================
# 静态 Schema 注册表（用于加密文件的 LLM Prompt 注入）
# =====================================================================

from dataclasses import dataclass, field


@dataclass
class ColumnInfo:
    """单列信息。"""
    col_index: int
    display_name: str          # 表头显示名称
    semantic: str              # 实际语义描述
    dtype: str                 # Pandas dtype 名称
    description: str           # 详细说明
    is_empty: bool = False     # 是否为始终为空的列


@dataclass
class RowCategory:
    """行分类标签定义。"""
    label: str                 # Col 3 中的标签值
    semantic: str              # 语义描述
    value_range: str = ""      # 数值范围描述
    example: str = ""          # 示例值


@dataclass
class SchemaInfo:
    """静态 Schema 信息，用于加密文件的 LLM Prompt 注入。"""
    sheet_name: str
    description: str
    total_rows: int
    total_cols: int
    header_row: int
    data_start_row: int
    columns: list[ColumnInfo]
    categories: list[RowCategory] = field(default_factory=list)
    sample_rows: list[list] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# CT 页静态 Schema（人工校验，高保真）
_CT_SCHEMA = SchemaInfo(
    sheet_name="CT",
    description="CT 良率及不良率 By 月/周/天 汇总报表",
    total_rows=1532,
    total_cols=15,
    header_row=3,
    data_start_row=4,
    columns=[
        ColumnInfo(0, "(空)", "空列", "object",
                   "始终为空列，读取时应删除", is_empty=True),
        ColumnInfo(1, "ProductCode", "产品型号", "str",
                   "纵向合并单元格，如 'C472'，标识产品型号"),
        ColumnInfo(2, "Operation", "制程站别", "str",
                   "纵向合并单元格，如 'CT'，标识制程站别"),
        ColumnInfo(3, "Factory", "指标分类标签", "str",
                   "**行级分类键**，决定该行数据的语义类型（见分类标签字典）"),
        ColumnInfo(4, "DefectGroup", "不良群组", "str",
                   "部分行有值，部分为空"),
        ColumnInfo(5, "(表头显示'项目/日期')", "不良Code", "str",
                   "⚠️ **重要修正**：表头为'项目/日期'，实际数据为不良代码（Defect Code）"),
        ColumnInfo(6, "M05", "月度汇总", "float64",
                   "5月份汇总值"),
        ColumnInfo(7, "W20", "周度汇总", "float64",
                   "第20周汇总值"),
        ColumnInfo(8, "5/4", "日数据", "float64",
                   "5月4日数据"),
        ColumnInfo(9, "5/5", "日数据", "float64",
                   "5月5日数据"),
        ColumnInfo(10, "5/6", "日数据", "float64",
                    "5月6日数据"),
        ColumnInfo(11, "5/7", "日数据", "float64",
                    "5月7日数据"),
        ColumnInfo(12, "5/8", "日数据", "float64",
                    "5月8日数据"),
        ColumnInfo(13, "5/9", "日数据", "float64",
                    "5月9日数据"),
        ColumnInfo(14, "5/10", "日数据", "float64",
                    "5月10日数据"),
    ],
    categories=[
        RowCategory("CT投入量", "CT站别投入数量", "≥ 0 整数", "86225.0"),
        RowCategory("CT良率", "CT站综合良率", "[0, 1]", "0.9343"),
        RowCategory("CT_A良率", "CT站 A 品良率", "[0, 1]", "0.8823"),
        RowCategory("31000_T良率占比", "31000_T 良率占比", "[0, 1]", "0.0"),
        RowCategory("CT投入量_MVI不良占比", "CT投入量的 MVI 不良占比", "[0, 1]", "0.206"),
        RowCategory("CLA2_G品占比", "CLA2 G品占比", "[0, 1]", "0.0"),
        RowCategory("CLA2投入量", "CLA2投入数量", "≥ 0 整数", "0.0"),
    ],
    sample_rows=[
        ["C472", "CT", "CT投入量", "", "", "86225.0", "1719.0", "14120.0", "20297.0",
         "19350.0", "16569.0", "6770.0", "4429.0", "1719.0"],
        ["C472", "CT", "CT良率", "", "", "0.9343", "0.7784", "0.9527", "0.9306",
         "0.9608", "0.9607", "0.8861", "0.8313", "0.7784"],
        ["C472", "CT", "CT_A良率", "", "", "0.8823", "0.7784", "0.9388", "0.8824",
         "0.8771", "0.8978", "0.8861", "0.6853", "0.7784"],
        ["C472", "CT", "31000_T良率占比", "", "", "0.0", "0.0", "0.0", "0.0",
         "0.0", "0.0", "0.0", "0.0", "0.0"],
        ["C472", "CT", "CT投入量_MVI不良占比", "", "", "0.2063", "0.9971", "0.0171",
         "0.0541", "0.1774", "0.2388", "0.4889", "0.9106", "0.9971"],
    ],
    notes=[
        "Col 5（不良Code）表头显示为'项目/日期'，实际为不良代码，这是关键修正",
        "Col 1（ProductCode）和 Col 2（Operation）存在纵向合并单元格",
        "Col 3（Factory）是行级分类标签，决定该行数据语义",
        "时间列层级：月(M05) → 周(W20) → 逐日(5/4~5/10)",
        "投入量类数据 COM 返回 float（如 86225.0），实际为整数",
    ],
)

# Schema 注册表：sheet_name -> SchemaInfo
_STATIC_SCHEMAS: dict[str, SchemaInfo] = {
    "CT": _CT_SCHEMA,
}


def _static_schema_to_markdown(info: SchemaInfo) -> str:
    """将 SchemaInfo 转换为高保真 Markdown 描述。

    Args:
        info: 静态 Schema 信息

    Returns:
        格式化的 Markdown 文本，可直接注入 LLM Prompt
    """
    lines: list[str] = []
    lines.append(f"【数据表元数据与高保真 Schema 结构 - 静态注入】")
    lines.append(f"- Sheet: {info.sheet_name}")
    lines.append(f"- 描述: {info.description}")
    lines.append(f"- 总行数: {info.total_rows}")
    lines.append(f"- 总列数: {info.total_cols}")
    lines.append(f"- 表头行: Row {info.header_row}")
    lines.append(f"- 数据起始行: Row {info.data_start_row}")
    lines.append(f"- 数据来源: 人工校验的静态 Schema（文件受企业加密保护）")
    lines.append("")
    lines.append("【字段定义（已人工修正）】")
    lines.append("| 列索引 | 表头显示 | 实际语义 | 数据类型 | 说明 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for col in info.columns:
        flag = " [修正]" if "重要修正" in col.description else ""
        empty_flag = " [空列]" if col.is_empty else ""
        lines.append(
            f"| Col {col.col_index} | {col.display_name} | {col.semantic}{flag}{empty_flag} "
            f"| {col.dtype} | {col.description} |"
        )
    lines.append("")

    if info.categories:
        lines.append("【行分类标签字典（Col 3 = Factory）】")
        lines.append("| 标签值 | 语义 | 数值范围 | 示例 |")
        lines.append("| --- | --- | --- | --- |")
        for cat in info.categories:
            lines.append(f"| {cat.label} | {cat.semantic} | {cat.value_range} | {cat.example} |")
        lines.append("")

    if info.sample_rows:
        # 确定列数
        n_cols = len(info.sample_rows[0])
        lines.append("【数据样例（前 5 行）】")
        # Build header
        col_headers = ["ProductCode", "Operation", "Factory(标签)", "DefectGroup",
                       "不良Code"] + [f"Col {i}" for i in range(6, 6 + n_cols - 5)]
        actual_headers = col_headers[:n_cols]
        lines.append("| " + " | ".join(actual_headers) + " |")
        lines.append("| " + " | ".join(["---"] * n_cols) + " |")
        for row in info.sample_rows:
            display_row = [str(v)[:20] if v else "" for v in row]
            lines.append("| " + " | ".join(display_row) + " |")
        lines.append("")

    if info.notes:
        lines.append("【重要说明】")
        for note in info.notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.append("【结构特征总结】")
    lines.append("- 二维交叉表：行 = (ProductCode × Operation × 指标分类), 列 = 时间(月→周→天)")
    lines.append("- Col 1 (ProductCode) 和 Col 2 (Operation) 存在纵向合并单元格，需 ffill 修复")
    lines.append("- Col 3 (Factory) 是行级分类键，决定该行数据语义类型")
    lines.append("- Col 5（不良Code）表头误导，实际数据为不良代码字符串")
    lines.append("- 时间列粒度：Col 6=月度, Col 7=周度, Col 8~14=逐日")

    return "\n".join(lines)


def _get_static_schema(sheet_name: str) -> str | None:
    """按 sheet 名称查找静态 Schema，返回 Markdown 格式描述。

    如果找不到对应 sheet 的静态 Schema，返回 None。
    """
    info = _STATIC_SCHEMAS.get(sheet_name)
    if info is None:
        return None
    return _static_schema_to_markdown(info)


def extract_schema(file_path: Path, nrows: int = 20) -> str:
    """从 Excel 文件提取高保真 Schema 结构描述。

    处理流程:
    1. 检测文件是否被企业加密软件加密（文件头魔数检查）
    2. 加密文件 → 优先查静态 Schema 注册表，回退 COM 动态读取
    3. 非加密文件 → pandas 读取 + 多级表头检测 + 前向填充修复
    4. 输出结构化 Markdown Schema 描述

    Args:
        file_path: Excel 文件路径
        nrows: 读取的数据行数（包含表头，仅 pandas 模式有效）

    Returns:
        结构化的 Markdown Schema 描述文本

    Raises:
        FileNotFoundError: 文件不存在
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # Step 0: 检测加密文件
    if _is_encrypted(file_path):
        logger.info(f"检测到加密文件: {file_path.name}，尝试静态 Schema 注入")
        # 尝试通过文件名推断 sheet 名称
        sheet_name = _detect_sheet_name_via_com(file_path)
        static = _get_static_schema(sheet_name)
        if static:
            logger.info(f"静态 Schema 命中: {sheet_name}")
            return static
        # 静态 Schema 未命中，回退 COM 动态读取
        logger.warning(f"静态 Schema 未找到 ({sheet_name})，回退 COM 动态提取")
        return _extract_schema_via_com(file_path, sheet_name, nrows)

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
