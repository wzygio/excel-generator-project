# 测试用例

## Case1-灵活业务

### Workflow
请分析C516近一周MVI产出占比的变化趋势：
1. 先下载“月周天良率数据表”
2. 从“CT”页寻找行表头为“MVI产出占比”的一行，该行即为你需要的数据。
    - hint：如果不明白可以查看spec\references\table_schema.json

### Acceptance Standards
1. 拿到MVI产出占比数据
2. 给出趋势分析

## Case2-固定流程测试

### Workflow
请完成“异常HL”

### Acceptance Standards
1. output下有“异常HL”结果

## Data Source
1. 月周天良率数据表
    - 文件名：V3良率及不良率By月周天汇总报表
    - Sheet名：“CT”
    - 获取方式：调用“FineReport Rpa”skill进行下载。筛选如下：
        * 结束日期：当日日期（示例：2026-06-11）
    - 表格结构：请查看表头寻找近一周的日期，一般为最后七列，sheet页为“CT””