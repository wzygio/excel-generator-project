# Task

接下来请开发一条Harness架构生成skill。

# Goal
调用该Skill后，能够根据每个项目，生成一份标准、有用（对于Codex）的Harness架构

# Context

我们利用Harness的目的是为了服务Codex开发，具体如下：
1. 让Codex能够更快速、更精准的理解项目
2. 让Codex能够精确的理解用户需求
3. 让Codex能够精确地把控开发方向

# Workflow

1. 请你先读取《工程技术：在智能体优先的世界中利用 Codex》这篇文章，了解Harness架构
2. 请你读取我的截图，我对Harness架构的总结如图所示，请你分析是否正确，如果不正确，请进行修改。
    - Goal：得到一份清晰的Harness架构。
3. 我在图中标注了Harness必须的部分，包括：AGENTS.md、系统架构（ARCHITECTURE.md）、设计规范、项目计划。请分析是否正确
    - Goal：确定你上面制定的Harness架构中，哪些是Harness架构的必须项。
4. 我在图中标注了Harness架构中每部分的类别，分为三类：自行维护、Agent维护、Codex已有。解释如下：
    - 自行维护：完全需要用户自行维护
    - Agent维护：可以在开发过程中让Codex维护
    - Codex已有：Codex已自带相关功能
    - Goal：确定你上面制定的Harness架构中，每个部分的属性
5. 请基于Step2-Step4的结果，构建出一份清晰的Harness蓝图，输出至：输出至：docs\design
6. 基于上述蓝图思考如何设计一份构建Harness的skill，要求如下：
    - 我们开发的skill，仅涉及“自行维护、Agent维护”这两项内容的构建。
    - 该skill即可以创建一个Harness框架，也可以修正当前项目的Harness框架（可以分别创建一个skill来完成这两种功能）
7. 计划制定完成后，输出至：docs\plans
8. 按照计划开发Skill
9. 完成后新建Worktree，并在其中应该您创建的Harness构建skill，来重构当前项目的Harness
10. 重构完成后，请你比较新旧框架，并告诉我优化原因

# Requirements

1. 我们的项目是基于Codex开发，所以生成的Harness系统要契合Codex
2. 我们要构建的是一份轻量级的Harness