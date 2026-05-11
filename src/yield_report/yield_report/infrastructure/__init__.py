# src/yield_report/yield_report/infrastructure/__init__.py
"""
良率报告领域基础设施层

职责:
- Excel 文件 IO 处理 (读取/写入)
- 源表数据提取
- Prompt 模板加载和管理
- Parquet 快照缓存

TODO: 在基础模块就绪后实现:
- ExcelReader:   源表数据读取
- ExcelWriter:   报告写入
- PromptLoader:  Prompt 模板管理
- SnapshotCache: Parquet 快照缓存
"""
