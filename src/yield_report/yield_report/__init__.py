# src/yield_report/yield_report/__init__.py
"""
良率报告领域 (Yield Report Domain)

本领域负责所有与良率日报相关的核心业务逻辑:
- application/:  应用服务层 (文件上传编排、分析流程编排、报告生成编排)
- core/:         核心领域层 (Gap分析、异常分析、趋势分析 —— 大模型重度参与)
- infrastructure/: 基础设施层 (Excel 文件 IO、数据提取、Prompt 模板加载)

开发顺序约束:
    按照 EPCC Flow 约定，Core 层的 LLM Prompt 交互规则将在
    Shared Kernel 和 UI 脚手架就绪后再集中实现。
"""
