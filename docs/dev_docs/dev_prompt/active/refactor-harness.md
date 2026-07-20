# Task：Harness重构

## Background
- 我重构了当前项目的Harness。将其全部移动至references目录下。
- 因为根据我的理解，Harness的本质就是Agent在各个开发阶段的references。因此我根据Agent的各个开发阶段重构了Harness。
- 这样可能并不准确，但便于我理解和管理。

---

## Step1：架构理解
- 请你先了解我设计的最新的Harness架构：
    * Harness当前架构:“references”
    * Harness完整架构：如图所示。但对于本项目来说，当前Harness已经足够使用。
- 输出一份Harness的完整架构图到如下路径：“D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev”：

---

## Step2：架构补全
- 重新扫描并补全Harness各个模块下的“index.md”：
    * 注意：index.md只存放文件夹路径，不再存放文件路径，以缩小维护成本。
- 扫描项目，并重构“ARCHITECTURE.md”
    * 注意：ARCHITECTURE.md只下探到当前项目的二级路径，便于codex快速了解项目。具体的定位追踪则交给codegraph。

---

## Step3：重构AGENTS.md
- 首先请搜索资料，请思考并理解AGENTS.md的设计规范。我认为它至少应该AGENTS.md应该遵守以下原则：
    * 绝不会因为业务和设计的改动而改动
    * 挂载机制：即Context Router，让Agent知道每个阶段应该看什么。具体来说，就是在合适的时间段把合适的信息挂载到上下文中。
    * 反馈机制：即Iteration Router，任务执行完成后修改Harness对应的部分，完成迭代。
- 将最新的AGENTS.md的设计规范输出到以下路径：“D:\wzy\Visionox-Docs_Backup\dev-docs\codex”
- 按照最新的原则，重构AGENTS.md，您可以参考以下建议。但请在移动之前，思考这些内容是否合理：
    * 我认为只需要保留：“Project Overview”和“Task Routing”
    * “Rules Boudary”应该移动至“references/design/system_design”
    * “Coding Conventions”应该移动至“references\dev_references\coding_spec”
    * “Safety Rules”应该移动至“references\dev_references\restrictions”
    * 删除掉原有的“Task Routing”，将现有的“Source of Truth”改为“Task Routing”

### Goal
重构后，请审查AGENTS.md是否符合设计规范。

---

## Step4：让Harness可运行
1.  请你查询github上有名的Harness开源项目，学习其中的理念，并为我设计一套Harness机制，并输出到如下路径：“D:\wzy\Visionox-Docs_Backup\dev-docs\codex”。设计时，您可以参考以下思路：
    * 我认为Harness的核心就是AGNTS.md的挂载机制和反馈机制，所以一套正确的Harness机制至少要兼容这两者。
    * 设计挂载机制时，你可以参考如下两种方案：
        - progressive disclosure：挂载至AGENTS.md，通过渐进式披露来让Agent自行获取。
        - hooks：生命周期事件触发
2. 按照你设计的机制，完善当前的Harness，让它变为一套确实可以迭代循环的Harness。
    - 我可以接受人工介入，但它必须要能够切实可行的助力项目开发，而不是变成开发文档记录库。
    - 我之所以将过去标准的Harness结构，降级成以3开发步骤为导向的架构，也是为了这一点。
3. 重构后，请执行一个任务：仿效“daily_report”，将“report_download”也封装成一个letta client tools模式的轻薄的“wrap skill”。它的本质应该是调用“FineReport Rpa”
    - Goal：不断迭代优化，直至重构的该skill能够完成烟测。

### Goal
不断迭代优化，直至完成任务后Harness的完成相应进化（总结）。

---

## Step5：修正Harness Builder Skill
1. 将“Harness Builder”skill转化为两个新skill，分别用于Harness创建和Harness重构。
2. 将最终版AGENTS.md和Harness的架构录入其中，将最终版AGENTS.md和Harness的机制录入其中。
    - 二者都需要有单独的配置文件，便于后续再次修改。
3. Harness重构skill功能如下：在其可以扫描一个项目后
    * 纠正Harness目录结构（可能为docs）。
    * 扫描已有Harness内容，识别无效文件（将其移动至一个单独的目录，但不要删除），移动有效文件至正确目录下。
    * 修改AGENTS.md的内容。
4. Harness新建skill功能如下：在其可以扫描一个项目后
    * 创建Harness目录结构。
    * 创建AGENTS.md和ARCHITECTURE.md。
    * 补全通用配置，例如“Coding Conventions”、“Safety Rules”等
    * 补全模块设计：“references/design/module_design”
5. 完成后请利用该skill优化如下路径下的repo中的Harness：“D:\wzy\Python\vivo-project”

### Goal
不断迭代优化该Skill，直到目标repo下的Harness架构与当前repo优化后的架构一致。

---

# Task：Harness优化

## Step0：优化AGENTS.md和references
1. AGENTS.md和references是否满足以下要求两条要求，如果不满足请进行优化：
    - AGENTS.md-TaskRouter：每个顶层 index 只路由到文件夹，不直接堆细节。
    - references-index.md：每个文件夹说明“何时读取、读哪些文件、对应哪些命令”。

## Step1：优化Observation
1. 请您查看当前的“output”中的结构，当前结构还不够清晰：
    - “decrypted_files、downloads、logs”这种系统级类型名称和“rpa_debug、rpa_downloads、task2_smoke”这种业务级类型名称混杂
2. 请您制定一套企业级的output架构，能够企业级项目所有可能的Runtime产出文件类别，让每一个产出文件都有清晰的存放位置。
    - 并将该架构输出至如下路径：“D:\wzy\Visionox-Docs_Backup\dev-docs\dev-system_arch”
3. 补充“coding_conventions.md”，增加如下规则：在编码时，将Runtime运行产物的输出路径设为“output”中的对应路径（这只是个描述，你编写规则时要写出文件类型与路径名称的映射）
    - 文件路径：“references\dev_references\coding_spec\coding_conventions.md”

## Step2: 优化Verify
1. 优化“observability.md”：您提到了“运行 pytest/ruff/pyright/harness_check/业务 smoke，生成简洁 observation”，是否可以这样理解：将output中有Observation价值的路径添加到observability.md中，让output中的产物能够被应用到Agent编码中的observation阶段。
    - 文件路径：“D:\wzy\Python\excel-generator-project\references\test_references\observability.md”

## Step3：优化Reflect
1. “retrospective.md”应该保存的是机制而不是结果：
    - 因为reflect的机制（Iteration Router机制）随着拓展会更加复杂，但却只有在结束阶段才会调用，因此不应该常驻上下文。
    - 文件路径：“D:\wzy\Python\excel-generator-project\references\retrospective.md”
    - 将原有的输出路径从“retrospective.md”转为：“D:\wzy\Python\excel-generator-project\references\generated”

# Workflow
请思考以上建议，并给出优化方案，然后执行优化
    
