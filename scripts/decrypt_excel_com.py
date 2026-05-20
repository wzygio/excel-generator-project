"""
COM 解密脚本：通过 Excel.Application 透明解密企业加密的 .xlsx 文件
用法：uv run python scripts/decrypt_excel_com.py
"""

import os
import sys
import traceback

# 目标文件（相对 project root）
REL_PATH = r"docs/project_files/V3良率及不良率By月周天汇总报表.xlsx"


def _decrypted_path(original_path: str) -> str:
    """在相同目录下生成解密后的文件名（原文件名_decrypted.xlsx）。"""
    dir_name = os.path.dirname(original_path)
    base_name = os.path.basename(original_path)
    name, ext = os.path.splitext(base_name)
    return os.path.join(dir_name, f"{name}_decrypted{ext}")


def main():
    # 获取项目根目录（脚本所在目录的上一级）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    target_path = os.path.abspath(os.path.join(project_root, REL_PATH))
    output_path = _decrypted_path(target_path)

    if not os.path.isfile(target_path):
        print(f"[ERROR] 文件不存在: {target_path}")
        sys.exit(1)

    if os.path.isfile(output_path):
        print(f"[WARN] 输出文件已存在，将被覆盖: {output_path}")

    print(f"[INFO] 源文件: {target_path}")
    print(f"[INFO] 输出文件: {output_path}")
    print(f"[INFO] 源文件大小: {os.path.getsize(target_path)} bytes")

    # 检查是否加密（非 PK 开头即为加密）
    with open(target_path, "rb") as f:
        magic = f.read(4)
    if magic == b"PK\x03\x04":
        print("[INFO] 文件已是标准 ZIP 格式（PK 头），可能未加密或已解密")

    import win32com.client

    excel = None
    wb = None
    try:
        print("[INFO] 启动 Excel.Application ...")
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        print("[INFO] 正在打开加密文件（Excel 透明解密）...")
        wb = excel.Workbooks.Open(target_path)

        print("[INFO] 正在另存为（不覆盖原文件）...")
        # 51 = xlOpenXMLWorkbook (无宏的 .xlsx)
        wb.SaveAs(output_path, FileFormat=51)
        wb.Close(SaveChanges=False)
        wb = None

        print(f"[SUCCESS] 解密完成，已保存至: {output_path}")
        print(f"[INFO] 解密后文件大小: {os.path.getsize(output_path)} bytes")
        print(f"[INFO] 原始加密文件未改动: {target_path}")

        # 验证：解密后文件应为 PK 开头
        with open(output_path, "rb") as f:
            magic_after = f.read(4)
        if magic_after == b"PK\x03\x04":
            print("[VERIFY] 解密验证通过：文件头为 PK（标准 ZIP/xlsx 格式）")
        else:
            print(f"[WARN] 解密后文件头异常: {magic_after.hex()}")

    except Exception as e:
        print(f"[ERROR] COM 操作失败: {e}")
        traceback.print_exc()
        sys.exit(1)
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

    print("[DONE] 脚本执行完毕")


if __name__ == "__main__":
    main()
