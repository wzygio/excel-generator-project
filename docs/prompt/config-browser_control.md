请帮我在当前 Windows 环境中为 OpenAI Codex 安装并配置两个浏览器自动化相关项目：

1. Playwright MCP
2. open-browser-use / browser-use 相关的 MCP 与 Codex Skill

请按以下要求执行：

【总目标】
为 Codex 同时安装：
- Playwright MCP server
- open-browser-use 的 MCP server
- open-browser-use 对应的 Codex skill（如果可安装）
并在安装完成后验证 Codex 可以识别这些 MCP / skill。

【环境检查】
请先检查当前环境是否已有以下命令：
- node -v
- npm -v
- npx -v
- codex --version
- codex mcp --help

如果缺少 Node.js / npm / npx，请明确告诉我需要安装 Node.js LTS。
如果缺少 codex CLI，请明确告诉我需要先安装或登录 Codex CLI。
不要跳过环境检查。

【第一部分：安装 Playwright MCP】
优先使用 Codex 官方 MCP 配置方式安装 Playwright MCP。

请执行或等效完成：

codex mcp add playwright -- npx -y @playwright/mcp@latest

然后运行：

codex mcp list

确认列表中存在 playwright。

如果 codex mcp add 命令失败，请改为手动编辑：
%USERPROFILE%\.codex\config.toml

加入或合并以下配置，不要覆盖我已有的其他配置：

[mcp_servers.playwright]
command = "npx"
args = ["-y", "@playwright/mcp@latest"]
startup_timeout_sec = 20
tool_timeout_sec = 120

保存后再次运行：
codex mcp list

【第二部分：安装 open-browser-use CLI】
请安装 open-browser-use：

npm i -g open-browser-use

安装后检查以下命令是否可用：

open-browser-use --help
obu --help

如果 obu 命令存在，请继续；如果只有 open-browser-use 命令存在，请记录实际可用命令，并在后续配置中使用可用命令。

然后执行初始化：

open-browser-use setup

如果 setup 因 Chrome Web Store 或浏览器扩展问题失败，请尝试：

open-browser-use setup beta

如果仍然失败，请不要强行继续，说明失败原因，并告诉我需要手动安装 Chrome 扩展或向公司 IT 申请放行相关地址。

【第三部分：安装 open-browser-use 的 Codex Skill】
请尝试为 Codex 安装 open-browser-use skill：

npx skills add iFurySt/open-browser-use -g -a codex --skill open-browser-use -y

然后检查：

npx skills ls -g -a codex

确认列表中存在 open-browser-use。

如果 npx skills 命令不存在或失败，请先判断是否需要安装对应的 skills CLI。
如果该 skill 安装方式已变更，请搜索当前项目文档或 npm 包说明，找到最新安装方式后再安装。
不要伪造成功结果。

【第四部分：配置 open-browser-use MCP】
优先使用 Codex MCP 命令添加：

codex mcp add open_browser_use -- obu mcp

如果 obu 不可用，但 open-browser-use 可用，请尝试：

codex mcp add open_browser_use -- open-browser-use mcp

然后运行：

codex mcp list

确认列表中存在 open_browser_use。

如果 codex mcp add 失败，请手动编辑：
%USERPROFILE%\.codex\config.toml

加入或合并以下配置之一：

如果 obu 可用：

[mcp_servers.open_browser_use]
command = "obu"
args = ["mcp"]
startup_timeout_sec = 30
tool_timeout_sec = 180

如果只有 open-browser-use 可用：

[mcp_servers.open_browser_use]
command = "open-browser-use"
args = ["mcp"]
startup_timeout_sec = 30
tool_timeout_sec = 180

注意：不要覆盖已有的 playwright 配置，也不要删除已有的其他 Codex 配置。

【第五部分：最终验证】
请最终执行：

codex mcp list

并告诉我当前识别到的 MCP servers。

然后请给出两个测试提示词，供我在 Codex 中手动验证：

1. 使用 playwright 打开 https://example.com，并告诉我页面标题。
2. 使用 open_browser_use 打开 https://example.com，并告诉我页面标题。

如果你能够直接运行 Codex 测试，也可以帮我测试，但如果需要登录、浏览器授权或人工确认，请暂停并告诉我该如何点击。

【输出要求】
请按以下格式汇报：
1. 环境检查结果
2. Playwright MCP 安装结果
3. open-browser-use CLI 安装结果
4. open-browser-use Skill 安装结果
5. open-browser-use MCP 配置结果
6. 最终 codex mcp list 输出
7. 如果有失败项，给出明确原因和下一步处理方法

请务必谨慎，不要把“命令执行失败”说成“安装成功”。