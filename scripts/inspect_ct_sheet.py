"""
通过 COM 直接读取加密 xlsx 中 "CT" 页的数据表结构（不落盘）。
用法：uv run python scripts/inspect_ct_sheet.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from collections import Counter

import win32com.client


def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    file_path = (
        project_root
        / "docs/project_files/V3良率及不良率By月周天汇总报表.xlsx"
    ).resolve()

    if not file_path.exists():
        print(f"[ERROR] 文件不存在: {file_path}")
        sys.exit(1)

    excel = None
    wb = None
    try:
        print(f"[INFO] 打开加密文件: {file_path}")
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        wb = excel.Workbooks.Open(str(file_path))

        # ---- Sheet 列表 ----
        sheet_names = []
        for s in wb.Sheets:
            sheet_names.append(s.Name)
        print(f"\n[INFO] 工作簿中共 {len(sheet_names)} 个 Sheet:")
        for i, name in enumerate(sheet_names, 1):
            print(f"  {i}. [{name}]")

        target = "CT"
        if target not in sheet_names:
            print(f"[ERROR] 找不到 sheet: {target}")
            print(f"可用 sheets: {sheet_names}")
            return

        ws = wb.Sheets(target)
        print(f"\n{'='*80}")
        print(f"Sheet: [{target}]")
        print(f"  最大行: {ws.UsedRange.Rows.Count}, 最大列: {ws.UsedRange.Columns.Count}")
        print(f"{'='*80}")

        max_row = ws.UsedRange.Rows.Count
        max_col = ws.UsedRange.Columns.Count

        # ---- 前 10 行预览 ----
        print(f"\n>>> 前 10 行预览（前 20 列）：")
        print("-" * 100)
        header_candidates = []
        for row_idx in range(1, min(11, max_row + 1)):
            row_vals = []
            non_empty = 0
            for col_idx in range(1, min(21, max_col + 1)):
                val = ws.Cells(row_idx, col_idx).Value
                if val is not None:
                    non_empty += 1
                display = str(val)[:40] if val is not None else ""
                row_vals.append(display)
            print(f"  Row {row_idx:>3}: {row_vals}")
            header_candidates.append((row_idx, non_empty))

        # 推断表头行（非空列最多的行）
        header_row = max(header_candidates, key=lambda x: x[1])[0]
        print(f"\n>>> 推测表头行: Row {header_row}")

        # ---- 完整表头结构 ----
        print(f"\n>>> 表头 Row {header_row} 完整结构（全部 {max_col} 列）：")
        print("-" * 100)
        headers: list[tuple[int, str | None]] = []
        for col_idx in range(1, max_col + 1):
            val = ws.Cells(header_row, col_idx).Value
            headers.append((col_idx, val))
            print(f"  Col {col_idx:>3}: {val}")

        # ---- 数据样例（表头后 5 行，前 15 列） ----
        print(f"\n>>> 数据样例（Row {header_row+1} ~ {header_row+5}, 前 15 列）：")
        print("-" * 100)
        data_start = header_row + 1
        for row_idx in range(data_start, min(data_start + 5, max_row + 1)):
            row_vals = []
            for col_idx in range(1, min(16, max_col + 1)):
                val = ws.Cells(row_idx, col_idx).Value
                display = str(val)[:30] if val is not None else ""
                row_vals.append(display)
            print(f"  Row {row_idx:>3}: {row_vals}")

        # ---- 合并单元格信息（前 10 个） ----
        print(f"\n>>> 合并单元格（前 10 个）：")
        print("-" * 60)
        merged = ws.MergeCells
        if merged:
            for i, mc in enumerate(ws.MergeAreas):
                if i >= 10:
                    print(f"  ... 还有更多")
                    break
                print(f"  {mc.Address}")

        # ---- 数据类型分布（前 50 行，前 20 列） ----
        print(f"\n>>> 数据类型分布（Row {data_start}~{min(data_start+49, max_row)}, 前 20 列）：")
        print("-" * 80)
        for col_idx in range(1, min(21, max_col + 1)):
            counter: Counter = Counter()
            for row_idx in range(data_start, min(data_start + 50, max_row + 1)):
                val = ws.Cells(row_idx, col_idx).Value
                if val is not None:
                    counter[type(val).__name__] += 1
            if counter:
                print(f"  Col {col_idx:>3}: {dict(counter)}")

        # ---- 数据总行数 ----
        print(f"\n>>> 数据总览")
        print(f"  标题行: Row {header_row}")
        print(f"  数据行: Row {header_row+1} ~ {max_row} （共 {max_row - header_row} 行）")
        print(f"  总列数: {max_col}")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
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


if __name__ == "__main__":
    main()
