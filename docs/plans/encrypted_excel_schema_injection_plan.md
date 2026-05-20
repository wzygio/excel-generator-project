# 加密 Excel 表结构记录 & LLM Prompt 注入方案

## 1. 背景

- 文件 [`V3良率及不良率By月周天汇总报表.xlsx`](docs/project_files/V3良率及不良率By月周天汇总报表.xlsx) 被企业加密软件**文件系统过滤驱动级加密**
- `openpyxl` / `pd.read_excel()` 均报 `BadZipFile`，无法直接读取
- 现有 `extract_schema()`（[`tests/analyze_yield/code_generator.py`](tests/analyze_yield/code_generator.py):147）依赖 `pd.read_excel()`，对加密文件完全失效
- **Col 6** 表头显示"项目/日期"但实际数据为**不良Code（Defect Code）**
- 用户需求：将正确的表结构记录下来，作为大模型分析的上下文传入

## 2. 方案选型

| 方案 | 复杂度 | 可靠性 | 推荐 |
|------|--------|--------|------|
| A: COM 实时读取 + 动态提取 schema | 高 | 中（依赖 Excel 进程） | ❌ |
| **B: 静态高保真 Schema 文档 + Prompt 注入** | **低** | **高（人工校验过）** | **✅** |
| C: 混合（COM 读取缓存 + 静态回退） | 中 | 高 | 可选增强 |

**推荐方案 B**: 人工校验并记录一份高保真的表结构定义文档，在 Prompt 构建时直接注入。

## 3. CT 页高保真 Schema 定义

### 3.1 元数据

| 属性 | 值 |
|------|-----|
| Sheet 名 | `CT` |
| 总行数 | 1532 |
| 总列数 | 15 |
| 表头行 | Row 3（Row 1 = 标题, Row 2 = 说明） |
| 数据起始行 | Row 4 |

### 3.2 列定义（已修正）

| 列索引 | 表头文本（Row 3） | 实际语义 | 数据类型 | 说明 |
|--------|-------------------|----------|----------|------|
| Col 1 | *(空)* | 空列 | - | 始终为空，读取时跳过 |
| Col 2 | `ProductCode / 产品型号` | **产品型号** | `str` | 纵向合并单元格，如 `C472` |
| Col 3 | `Operation / 站别` | **制程站别** | `str` | 纵向合并单元格，如 `CT` |
| Col 4 | `Factory / 工厂名称` | **指标分类标签** | `str` | **关键列**，承载行级分类标签 |
| Col 5 | `DefectGroup / 不良群组` | **不良群组** | `str` | 部分行有值 |
| **Col 6** | `(显示为"项目/日期")` | **⚠️ 不良Code** | `str` | **表头误导**，实际为具体不良代码 |
| Col 7 | `M05` | **月度汇总** | `float` | 5月汇总值 |
| Col 8 | `W20` | **周度汇总** | `float` | 第20周汇总值 |
| Col 9 | `5/4` | **日数据** | `float` | 5月4日 |
| Col 10 | `5/5` | **日数据** | `float` | 5月5日 |
| Col 11 | `5/6` | **日数据** | `float` | 5月6日 |
| Col 12 | `5/7` | **日数据** | `float` | 5月7日 |
| Col 13 | `5/8` | **日数据** | `float` | 5月8日 |
| Col 14 | `5/9` | **日数据** | `float` | 5月9日 |
| Col 15 | `5/10` | **日数据** | `float` | 5月10日 |

### 3.3 行分类标签（Col 4 的语义字典）

Col 4（Factory / 指标分类标签）承载以下分类，决定了该行数据的具体含义：

| 标签值 | 语义 | Col 7-15 数据类型 | 示例值 |
|--------|------|-------------------|--------|
| `CT投入量` | CT站别投入数量 | `float`（正整数） | `86225.0` |
| `CT良率` | CT站综合良率 | `float`（0~1） | `0.9343` |
| `CT_A良率` | CT站 A 品良率 | `float`（0~1） | `0.8823` |
| `31000_T良率占比` | 31000_T 良率占比 | `float`（0~1） | `0.0` |
| `CT投入量_MVI不良占比` | CT投入量的 MVI 不良占比 | `float`（0~1） | `0.206` |
| `CLA2_G品占比` | CLA2 G品占比 | `float`（0~1） | `0.0` |
| `CLA2投入量` | CLA2投入数量 | `float`（正整数） | `0.0` |
| *(更多)* | 其他指标 | `float` | - |

### 3.4 数据行模式示例

```
Row 3:  [ 空  | ProductCode | Operation | Factory(标签) | DefectGroup | 不良Code |  M05  |  W20  | 5/4  | ... ]
Row 4:  [ 空  |   C472      |    CT     |  CT投入量     |    (空)     |  (空)    | 86225 | 1719  | 14120| ... ]
Row 5:  [ 空  |  (继承C472) |  (继承CT) |  CT良率       |    (空)     |  (空)    | 0.934 | 0.778 | 0.953| ... ]
Row 6:  [ 空  |  (继承C472) |  (继承CT) |  CT_A良率     |    (空)     |  (空)    | 0.882 | 0.778 | 0.939| ... ]
...
Row N:  [ 空  |   (新型号)  |   (新站)  |  (新标签)     |    (值)     |  (值)    | ...   | ...   | ...  | ... ]
```

### 3.5 结构特征总结

```
┌──────────────────────────────────────────────────────────────────────┐
│  二维交叉表设计                                                       │
│                                                                      │
│  行维度 (Row 4~1532):  ProductCode × Operation × Factory(指标分类)    │
│  列维度 (Col 7~15):    月度(M05) → 周度(W20) → 逐日(5/4~5/10)       │
│                                                                      │
│  特殊列:                                                              │
│    Col 2 (ProductCode) 和 Col 3 (Operation) 存在纵向合并单元格        │
│    Col 5 (DefectGroup) 在某些行有值, 某些行为空                       │
│    Col 6 (不良Code)     表头显示"项目/日期", 实际为不良代码代码       │
│    Col 4 (Factory)      是**行分类键**, 决定该行数据的语义类型         │
└──────────────────────────────────────────────────────────────────────┘
```

## 4. Prompt 注入方案

### 4.1 新增数据结构

在 [`tests/analyze_yield/code_generator.py`](tests/analyze_yield/code_generator.py) 中新增:

```python
# 文件加密检测常量
ENCRYPTED_FILE_MAGIC = b"\x00\x00\x00\x00"  # 加密文件头特征

# 静态 Schema 注册表: sheet_name -> SchemaInfo
_STATIC_SCHEMAS: dict[str, "SchemaInfo"] = {
    "CT": SchemaInfo(...)
}
```

### 4.2 修改 `extract_schema()` 逻辑

```python
def extract_schema(file_path: Path, nrows: int = 20) -> str:
    # Step 0: 检测文件是否为加密文件
    if _is_encrypted(file_path):
        sheet_name = _detect_sheet_name(file_path)  # 通过 COM 获取
        static = _get_static_schema(sheet_name)
        if static:
            return static.to_markdown()
        # 无静态 Schema 时回退 COM 读取
        return _extract_schema_via_com(file_path, nrows)
    
    # 原有逻辑: pd.read_excel()
    ...
```

### 4.3 `build_prompt()` 调用链

```
build_prompt()
  └─ schema = extract_schema(file_path)   ← 加密文件走静态/COM
  └─ prompt = CLAUDE_SYSTEM_PROMPT + schema + user_demand
  └─ subprocess.run(claude, prompt)
```

### 4.4 加密文件检测函数

```python
def _is_encrypted(file_path: Path) -> bool:
    """通过文件头魔数检测是否为加密文件。"""
    with open(file_path, "rb") as f:
        magic = f.read(4)
    return magic != b"PK\x03\x04"
```

## 5. 实施步骤

| 步骤 | 内容 | 产出 | 负责模式 |
|------|------|------|----------|
| 1 | 创建静态 Schema 文档 | [`docs/design/ct_sheet_schema.md`](docs/design/ct_sheet_schema.md) | Code |
| 2 | 修改 `extract_schema()` 支持加密文件检测 + 静态回退 | 修改 [`code_generator.py`](tests/analyze_yield/code_generator.py) | Code |
| 3 | 添加 `_is_encrypted()` / `_get_static_schema()` / `SchemaInfo` | 同上 | Code |
| 4 | 添加 COM 回退读取 `_extract_schema_via_com()` | 同上（可选） | Code |
| 5 | 验证：测试加密文件的 schema 提取流程 | 测试输出 | Code |

## 6. 红线约束

- R03: Core 层严禁直接依赖 Infrastructure — 本次修改在 `tests/` 目录（测试层），不触及红线
- R07: 类型标注强制 — 所有新增函数必须包含完整类型标注
