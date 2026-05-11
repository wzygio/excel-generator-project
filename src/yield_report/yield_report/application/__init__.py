# src/yield_report/yield_report/application/__init__.py
"""
应用服务层 (Application Service Layer)

职责:
- 协调上传、提取、分析、生成的完整编排流程
- 调用 Core 层的分析模块和 Infrastructure 层的 IO 模块
- 管理事务和工作流状态

TODO: 在基础模块就绪后实现以下编排器:
- ReportOrchestrator: 全流程编排 (上传 → 提取 → 分析 → 生成)
"""
