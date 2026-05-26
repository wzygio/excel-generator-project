# 配置路径差异详解：Claude Code、Codex CLI 与 .agents 的 Plugin 体系

> 本文基于对三条路径的完整文件树探索，逐一回答 Question 1 中的四个子问题。

---

## 1. 三条路径的系统解释

### 路径 A：C:\Users\V0141351\.claude\plugins

这是 **Claude Code（CC）的官方插件根目录**。Anthropic 将插件系统设计为「marketplace → plugin cache」的两层架构：

| 子目录 | 作用 |
|--------|------|
| marketplaces/ | 本地克隆的 marketplace 仓库（marketplace = 插件目录/商店），定义「有哪些插件可用」 |
| cache/ | 已安装插件的实际文件缓存（下载/解压后的插件源码） |
| data/ | 插件运行时产生的持久化数据 |
| installed_plugins.json | 已安装插件清单（名称、版本、安装路径、git SHA） |
| known_marketplaces.json | 已注册的 marketplace 来源（GitHub 仓库地址） |

**当前状态：**
- 注册了 2 个 marketplace：claude-plugins-official（Anthropic 官方）和 superpowers-marketplace（第三方社区）
- 安装了 1 个插件：superpowers@superpowers-marketplace v5.1.0

### 路径 B：C:\Users\V0141351\.agents\plugins

这是 **Codex CLI 的「个人插件」注册目录**。这是 Codex 独有的概念——不同于 CC 的 marketplace 体系，Codex 允许用户在本地直接创建/注册插件，无需通过 marketplace 分发。

**当前状态：**
- 注册了 1 个本地插件：rontend-toolkit
- 该插件包含 .codex-plugin/plugin.json + .mcp.json（定义了 v0、shadcn-ui、playwright 三个 MCP server）
- marketplace.json 定义了一个名为 personal 的 marketplace，源类型为 local

### 路径 C：C:\Users\V0141351\.codex\plugins

这是 **Codex CLI 的核心插件运行时目录**。结构远比 CC 复杂，分为四大区域：

| 子目录 | 作用 |
|--------|------|
| cache/openai-bundled/ | OpenAI 官方内置插件（Browser、Chrome 扩展宿主），随 Codex 版本分发 |
| cache/superpowers-marketplace/ | 从 CC 兼容 marketplace 安装的第三方插件缓存（与 CC 的 cache 结构完全相同） |
| .marketplace-plugin-source-staging/ | marketplace 插件安装时的源码暂存区（14 个随机名临时目录） |
| （内存/配置中） | 个人插件直接注册（.agents/plugins 下的 frontend-toolkit） |

---

## 2. .agents 真的能被 CC 和 Codex 都识别吗？

**答案是：部分共享，但不完全等价。**

### 证据分析

从文件树可以看出：

- **.agents 下有 skills/ 目录**（从 skills-lock.json 可以看出托管了 14 个 Matt Pocock 的技能，如 caveman、diagnose、tdd 等）
- **.agents 下有 plugins/ 目录**，其中 rontend-toolkit 使用的是 .codex-plugin/plugin.json 格式

### 技能（Skills）层面：高度共享

.agents/skills/ 目录中的技能可以被 **Codex 和 Claude Code 同时识别**。原因：

1. 两个工具都遵循 AGENTS.md 规范，其中 skills/ 目录是约定的技能存放路径
2. skills-lock.json 中记录的技能源（mattpocock/skills）是两个工具通用的 GitHub 技能仓库
3. 技能的 SKILL.md 格式在两个工具间是兼容的

### 插件（Plugins）层面：互不兼容

.agents/plugins/ 中的插件使用的是 Codex 的 .codex-plugin/plugin.json 格式（包含 mcpServers、interface 等 Codex 特有字段）。Claude Code 使用的是 .claude-plugin/plugin.json 格式。两者在插件层面的 **manifest 格式不同**，不能互相识别。

### 结论

| 层面 | CC 识别 .agents | Codex 识别 .agents | 共享程度 |
|------|-------------------|----------------------|----------|
| Skills（SKILL.md） | ✅ 是 | ✅ 是 | 完全共享 |
| Plugins（plugin.json） | ❌ 否（用 .claude-plugin） | ✅ 是（用 .codex-plugin） | 互不兼容 |

.agents 本质上是 Codex 引入的「用户级共享目录」，但 CC 只在 skills 层面与之互通，插件体系各自独立。

---

## 3. Claude Code 的 Plugins 文件树详解

### 3.1 Marketplace 概念

**Marketplace（插件市场）= 一个 GitHub 仓库，里面列出了若干个可安装的插件。**

它不是商店 App Store，而是一个 **JSON 目录文件**。每个 marketplace 仓库的 .claude-plugin/marketplace.json 定义了：

`json
{
  "name": "superpowers-marketplace",
  "plugins": [
    {
      "name": "superpowers",
      "source": { "source": "url", "url": "https://github.com/obra/superpowers.git" },
      "version": "5.1.0"
    },
    { "name": "superpowers-chrome", "source": ... },
    { "name": "elements-of-style", "source": ... }
    // ... 共 10 个插件
  ]
}
`

**工作流程：**
1. 用户执行 /plugin install superpowers@superpowers-marketplace
2. CC 读取 known_marketplaces.json，找到 superpowers-marketplace = github.com/obra/superpowers-marketplace
3. 克隆 marketplace 仓库到 marketplaces/superpowers-marketplace/
4. 读取 marketplace.json，找到 superpowers 插件的源地址 github.com/obra/superpowers.git
5. 克隆插件源码到 cache/superpowers-marketplace/superpowers/5.1.0/
6. 写入 installed_plugins.json

### 3.2 Superpowers 的本质

**Superpowers = 纯 Skills 集合，不是 MCP。**

从 plugin.json（.claude-plugin/plugin.json）可以看出：

`json
{
  "name": "superpowers",
  "version": "5.1.0",
  "description": "Core skills library for Claude Code: TDD, debugging, collaboration patterns",
  "keywords": ["skills", "tdd", "debugging", "collaboration", "best-practices", "workflows"]
}
`

- **没有 mcpServers 字段** — 它不是 MCP server
- **没有 hooks 配置** — 不注册任何 hook
- **仅有 skills/ 目录**（14 个技能：brainstorming、writing-plans、test-driven-development、systematic-debugging 等）

Superpowers 是一个「方法论框架」，通过 SKILL.md 文本指令指导 Agent 的工作方式。它依赖的是 **提示词工程（prompt engineering）**，而非 MCP 协议的工具调用。

**Superpowers 的源文件位置：**
- 源头：https://github.com/obra/superpowers.git（GitHub 公开仓库）
- CC 缓存：C:\Users\V0141351\.claude\plugins\cache\superpowers-marketplace\superpowers\5.1.0\
- Codex 缓存：C:\Users\V0141351\.codex\plugins\cache\superpowers-marketplace\superpowers\5.1.0\（内容完全相同）

### 3.3 双 manifest 机制的奥秘

Superpowers v5.1.0 的安装目录同时包含 .claude-plugin/plugin.json 和 .codex-plugin/plugin.json：

| 文件 | 用途 |
|------|------|
| .claude-plugin/plugin.json | 给 Claude Code 读的（仅含 name/version/description/keywords） |
| .codex-plugin/plugin.json | 给 Codex CLI 读的（额外包含 skills: "./skills/" 路径声明和完整的 interface UI 元数据） |

这就是为什么同一个插件安装包能同时被两个工具使用——**插件作者维护了两份 manifest**，每份针对不同工具的格式要求。

---

## 4. Codex 的 Plugins 文件树——与 Claude Code 的关键差异

### 4.1 三层插件来源

Codex 的插件系统有三条独立的加载路径，与 CC 的纯 marketplace 模型截然不同：

`
Codex 插件体系
├── ① openai-bundled/     ← 官方内置（随 Codex 版本分发，用户不可卸载）
│   ├── browser/          ← 浏览器自动化插件（skills + MCP）
│   └── chrome/           ← Chrome 扩展宿主（extension-host）
│
├── ② marketplace cache/  ← 从 CC 兼容 marketplace 安装的第三方插件
│   └── superpowers-marketplace/superpowers/5.1.0/
│
└── ③ .agents/plugins/    ← 用户本地创建的个人插件（不依赖 marketplace）
    └── frontend-toolkit/ ← MCP servers: v0 + shadcn + playwright
`

### 4.2 核心差异对比

| 维度 | Claude Code | Codex CLI |
|------|-------------|-----------|
| 插件来源 | 仅 marketplace（GitHub 仓库） | marketplace + 官方内置 + 本地个人 |
| manifest 格式 | .claude-plugin/plugin.json | .codex-plugin/plugin.json |
| MCP 集成 | 通过 hooks 注册 | 直接在 plugin.json 声明 mcpServers |
| 个人插件 | 不支持 | 支持（.agents/plugins/） |
| marketplace 注册 | known_marketplaces.json | 也使用 CC 兼容的 marketplace |
| UI 元数据 | 无 | interface 字段（displayName、category、brandColor 等） |

### 4.3 openai-bundled 的独特之处

Codex 的 cache/openai-bundled/ 是 CC 完全没有的概念：

- **Browser 插件**：包含 SKILL.md 技能文件 + MCP server 配置，实现了 Codex 内嵌浏览器的自动化能力
- **Chrome 插件**：包含 Chrome 扩展宿主（extension-host/），用于在 Codex 桌面应用中加载 Chrome DevTools Protocol
- **版本号** 26.519.31651 与 Codex 桌面应用版本绑定，用户无法独立更新

### 4.4 个人插件的创新

rontend-toolkit 展示了 Codex 独有的「零成本插件」模式：

`json
// .codex-plugin/plugin.json
{
  "name": "frontend-toolkit",
  "mcpServers": "./.mcp.json"  // 直接引用 MCP 配置
}

// .mcp.json
{
  "mcpServers": {
    "v0": { "command": "npx", "args": ["-y", "v0-mcp@latest"] },
    "shadcn-ui": { "command": "npx", "args": ["-y", "shadcn-mcp@latest"] },
    "playwright": { "command": "npx", "args": ["-y", "playwright-mcp@latest"] }
  }
}
`

用户只需创建两个 JSON 文件，无需 GitHub 仓库、无需 marketplace，即可将任意 MCP server 注册为 Codex 插件。这在 CC 中需要走完整的 marketplace 发布流程。

---

## 总结：三条路径的角色定位

`
C:\Users\V0141351\
├── .claude\                    ← Claude Code 的独立领地
│   └── plugins\                ← 纯 marketplace 驱动的插件系统
│       ├── marketplaces\       ← 插件目录定义
│       └── cache\              ← 插件安装缓存
│
├── .codex\                     ← Codex CLI 的核心领地
│   └── plugins\
│       ├── cache\openai-bundled\  ← (独有) 官方内置插件
│       ├── cache\superpowers-marketplace\ ← (共享) 兼容 CC marketplace
│       └── .marketplace-plugin-source-staging\ ← (独有) 安装暂存
│
└── .agents\                    ← (Codex 创建的) 用户级共享桥
    ├── skills\                 ← ✅ CC 和 Codex 都能读取的技能
    └── plugins\                ← ❌ 仅 Codex 能识别的个人插件
        └── frontend-toolkit\   ← 本地 MCP 插件（CC 不可见）
`

**关键理解：**
- .agents/skills/ 是 CC 和 Codex 之间唯一的「真正共享」区域
- CC 的插件世界是 marketplace 一元论
- Codex 的插件世界是 marketplace + 官方内置 + 个人创建的三元体系
- 同一个 Superpowers 安装包通过双 manifest（.claude-plugin + .codex-plugin）同时兼容两个工具
