"""
src/yield_report/yield_report/core/__init__.py

核心领域层 (Core Domain Layer)

本模块是系统中大模型重度参与的分析逻辑所在。
每个分析模块的文件顶部必须包含:
1. 该程序的详细业务解释
2. 如果调用了大模型，必须显式列出使用的完整 prompt

待实现的分析模块：
- gap_analysis.py:     日良率 Gap 分析 + 批次恶化判断
- exception_analysis.py: CT 异常解析 (新增异常 + 已知异常)
- trend_analysis.py:    连续三日/三周趋势分析

开发顺序:
    按照 EPCC Flow 约定，本层模块将在 Shared Kernel 和 UI 脚手架
    就绪后集中实现。
"""
