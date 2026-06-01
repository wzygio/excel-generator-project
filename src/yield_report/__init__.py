# src/yield_report/__init__.py
"""
yield_report: 良率日报生成系统

包结构:
- agent/:         Codex/Runtime 调用契约、Spec 路由、轻量运行时
- skills/:        纵向业务 Skill（报表下载、数据分析、日报生成）
- application/:   应用服务层（报告生成编排）
- core/:          核心领域层（查询解析、LLM 分析）
- infrastructure/: 基础设施层（文件加载、外部服务适配）
"""
