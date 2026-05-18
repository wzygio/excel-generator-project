# Skill 提案：LLM 结构化参数提取（无 LangChain）

## 问题描述
在 DDD 架构中，需要将用户的自然语言输入（如"帮我下载今天的V3良率报表"）转换为结构化的查询参数（报表类型、日期、产品型号等），然后调用对应的数据获取模块。是否需要引入 LangChain 等重型框架？

## 根因分析
LangChain 提供的 Tool/Agent 抽象适合构建复杂的多步推理链，但当需求仅仅是"从自然语言中提取结构化参数"时，引入 LangChain 会带来不必要的抽象层和依赖体积。

## 解决方案
使用 **LLM 原生 JSON Mode** + **Pydantic V2 模型** 直接完成参数提取，无需 LangChain。

### 关键代码片段

```python
from pydantic import BaseModel, Field
from enum import Enum

class ReportType(str, Enum):
    DAILY_YIELD = "daily_yield"
    BATCH_YIELD = "batch_yield"
2
class ReportQueryRequest(BaseModel):
    report_type: Optional[ReportType] = Field(default=None, description="报表类型")
    start_date: Optional[str] = Field(default=None, description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="结束日期 YYYY-MM-DD")
    product_models: Optional[list[str]] = Field(default=None, description="产品型号列表")
    user_intent: str = Field(default="", description="用户意图描述")
```

使用方式（通过 `LLMManager.chat()` 传递 `response_format={"type": "json_object"}`）：

```python
response_text = llm_manager.chat(
    provider="deepseek",
    messages=[{"role": "user", "content": user_input}],
    system_prompt=SYSTEM_PROMPT,  # 包含报表类型说明和参数提取规则
    temperature=0.1,
    response_format={"type": "json_object"},
)
data = json.loads(response_text)
request = ReportQueryRequest(**data)  # Pydantic 强类型校验
```

### 核心技术点
1. **System Prompt 设计**：包含所有报表类型的中文名称、描述、同义词映射，以及日期提取规则
2. **低温度（0.1）**：确保输出确定性
3. **JSON Mode**：强制 LLM 输出合法 JSON，支持 DeepSeek 原生
4. **Pydantic V2 校验**：双重保障——LLM 输出 JSON，Pydantic 做类型和格式校验
5. **`_clean_response()`**：防御性清理，移除 LLM 可能添加的 ```json 代码块标记

## 验证方法
```python
parser = QueryParser()
request = parser.parse("帮我下载今天的V3良率报表")
assert request.report_type == ReportType.DAILY_YIELD
assert request.end_date is not None
```

## 建议插入 skills/README.md 的位置
作为新技能条目，分类为"LLM 交互模式"，命名为 `llm-structured-param-extraction`
