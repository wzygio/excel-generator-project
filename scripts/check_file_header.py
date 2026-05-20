"""检查解密文件的实际文件头字节和 ZIP 结构。"""
import os
import zipfile

base = r"d:\wzy\Python\excel-generator-project\docs\project_files"

files = [
    "V3良率及不良率By月周天汇总报表.xlsx",
    "V3良率及不良率By月周天汇总报表_decrypted.xlsx",
]

for fname in files:
    path = os.path.join(base, fname)
    if not os.path.isfile(path):
        print(f"[SKIP] {fname}: 不存在")
        continue
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(16)
    print(f"[FILE] {fname}")
    print(f"  Size: {size} bytes")
    print(f"  Head: {head.hex()}  ({head!r})")
    try:
        with zipfile.ZipFile(path, "r") as z:
            names = z.namelist()
            print(f"  ZIP OK! 内含 {len(names)} 个条目")
            for n in names[:10]:
                print(f"    - {n}")
            if len(names) > 10:
                print(f"    ... 还有 {len(names)-10} 个")
    except Exception as e:
        print(f"  ZIP FAIL: {e}")
    print()
