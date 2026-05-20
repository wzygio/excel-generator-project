# Skill 提案：加密 Excel 的静态 Schema 注入方案

## 问题描述

企业加密软件（文件系统过滤驱动级加密）对所有 .xlsx 文件透明加密，导致 `openpyxl` / `pd.read_excel()` 全部报 `BadZipFile`。COM 方式虽然可以读取，但无法将解密后的文件保存到磁盘（过滤驱动会重新加密写入）。现有 `extract_schema()` 函数依赖 `pd.read_excel()`，对加密文件完全失效。

## 根因分析

1. 企业加密软件在文件系统过滤驱动层工作，所有磁盘读写均被拦截
2. Excel.exe 等白名单进程可透明解密，但写入时仍被重新加密
3. Python（openpyxl/pandas）不在白名单中，直接 `read_excel()` 失败
4. COM 通过 `SaveAs` 保存的文件依然加密，无法被 Python 直接读取

## 解决方案

采用**静态 Schema 注册表 + Prompt 注入**策略：

### 核心思路

```
加密文件 detect (文件头魔数)
  ├─ 是 → 查静态 Schema 注册表 (sheet_name → SchemaInfo)
  │     ├─ 命中 → 返回人工校验的 Markdown Schema
  │     └─ 未命中 → COM 动态读取 (回退)
  └─ 否 → 原有 pd.read_excel() 逻辑
```

### 关键实现

```python
# 文件头检测
_PK_ZIP_HEADER = b"PK\x03\x04"

def _is_encrypted(file_path: Path) -> bool:
    with open(file_path, "rb") as f:
        return f.read(4) != _PK_ZIP_HEADER

# 静态 Schema 注册
@dataclass
class SchemaInfo:
    sheet_name: str
    columns: list[ColumnInfo]    # 列定义（含语义修正）
    categories: list[RowCategory]  # 行分类标签字典
    sample_rows: list[list]      # 数据样例
    notes: list[str]             # 重要说明

# 注入到 extract_schema()
def extract_schema(file_path, nrows=20):
    if _is_encrypted(file_path):
        static = _get_static_schema(sheet_name)
        if static:
            return static  # 返回高保真 Markdown
        return _extract_schema_via_com(file_path, sheet_name, nrows)
    # 原有 pandas 逻辑...
```

### 修正表头误导

在 CT 页中，Col 6 表头显示"项目/日期"，实际为**不良Code**。静态 Schema 中通过 `ColumnInfo.semantic` 字段人工纠正：

```python
ColumnInfo(5, "(表头显示'项目/日期')", "不良Code", "str",
           "重要修正：表头为'项目/日期'，实际数据为不良代码"),
```

## 验证方法

```python
# 1. 加密检测
assert _is_encrypted(encrypted_xlsx_path) is True
assert _is_encrypted(normal_xlsx_path) is False

# 2. 静态 Schema 注入
result = extract_schema(encrypted_xlsx_path)
assert "不良Code [修正]" in result
assert "静态注入" in result

# 3. 非加密文件原有逻辑不变
result = extract_schema(normal_xlsx_path)
assert "静态注入" not in result
```

## 涉及文件

| 文件 | 变更 |
|------|------|
| [`tests/analyze_yield/code_generator.py`](tests/analyze_yield/code_generator.py) | 新增 `_is_encrypted()`, `SchemaInfo`, `_STATIC_SCHEMAS`, `_static_schema_to_markdown()`, `_get_static_schema()`, `_extract_schema_via_com()`, `_detect_sheet_name_via_com()`；修改 `extract_schema()` |
| [`docs/design/ct_sheet_schema.md`](docs/design/ct_sheet_schema.md) | 新增：CT 页高保真 Schema 定义文档 |

## 建议插入 skills/README.md 的位置

在"加密 Excel 的 COM 透明解密方案"之后，作为该方案的扩展/配套方案。
