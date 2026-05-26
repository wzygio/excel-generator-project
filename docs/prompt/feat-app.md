你现在是一个极其严谨的“高级前端平台工程师兼自动化运维专家”。我的最终目标是在本地电脑上完美运行并预览刚刚由 Google AI Studio 生成的 React 组件文件 `YieldAgentDashboard.jsx`。

为了能够100%成功渲染并避免任何环境报错，请在终端（Terminal）中分步指挥或直接通过脚本为我配置好全套的本地开发环境。

请遵循以下核心执行逻辑：

【1. 技术栈选型】
我们不使用老旧沉重的 create-react-app。请引导我使用现代最轻量、极速的【Vite】来搭建 React 环境。

【2. 依赖精准对齐】
仔细观察我的 `YieldAgentDashboard.jsx` 的源码头部，它依赖了以下生态，请确保它们被完整安装：
- 核心框架：React
- 样式系统：Tailwind CSS (及其依赖 postcss, autoprefixer)
- 图标库：lucide-react (代码中大量使用了如 Play, Terminal, Database 等图标)

【3. 具体的环境配置路径（请引导我完成）】
请在你的回复中，给出清晰的、在 Windows PowerShell 或 macOS 终端中可以直接复制运行的命令：

  步骤 A：初始化 Vite 项目
  - 创建一个名为 `yield-agent-ui` 的标准 React (JavaScript) 项目，并进入该目录。

  步骤 B：安装必需依赖
  - 一键安装 `lucide-react`。
  - 安装 Tailwind CSS 的全套开发依赖，并生成 `tailwind.config.js` 和 `postcss.config.js`。

  步骤 C：配置 Tailwind 的扫描路径
  - 明确告诉我如何修改 `tailwind.config.js` 中的 `content` 数组，使其包含 `./index.html` 和 `./src/**/*.{js,ts,jsx,tsx}`，否则 Tailwind 的样式无法生效。
  - 告诉我应该在哪个 CSS 文件（通常是 `src/index.css`）的最顶部写入三行 `@tailwind` 指令。

  步骤 D：代码替换指南
  - 提示我把现有的 `YieldAgentDashboard.jsx` 里的全部内容，去覆盖项目中的 `src/App.jsx` 文件（或者直接重命名替换）。

  步骤 E：启动与预览
  - 给出启动本地开发服务器的命令（`npm run dev`），并说明如何在浏览器中打开本地链接进行查看。

【你的回复约束】
请保持语气专业、指令清晰。命令与命令之间要有明确的解释，不要一次性吐出一万行代码让用户迷茫。每一步都要有防错提示（例如提示用户检查 Node.js 是否已安装）。

现在，请开始你的本地环境配置指导。