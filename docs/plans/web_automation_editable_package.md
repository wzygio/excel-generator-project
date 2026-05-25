# web_automation 可编辑包发布

## 背景

`cell-projects/packages/` 下的 `common_utils` 和 `web_automation` 原本通过 workspace 内部约定导入
（`from packages.xxx.src.yyy import ...`），仅能在 `cell-projects` 内使用。
为支持跨项目复用，将其转换为标准 Python 包并通过 `pip install -e` 安装。

## 包信息

| 项目 | 包名 | 路径 | 说明 |
|------|------|------|------|
| common_utils | `fr-common-utils` | `packages/common_utils/` | ITaskEngine 接口、DB、日志、邮件工具 |
| web_automation | `fr-web-automation` | `packages/web_automation/` | FineReport RPA 核心（登录、搜索、下拉选择、导出） |

## 目录结构变更

**变更前：** `src/` 扁平结构，文件直接在 `src/` 下

```
packages/web_automation/src/
├── adapter.py
├── config.py
├── application/
│   └── download_service.py
└── infrastructure/
    ├── browser_manager.py
    └── playwright_adapter.py
```

**变更后：** `src/包名/` 嵌套结构

```
packages/web_automation/src/fr_web_automation/
├── __init__.py
├── adapter.py
├── config.py
├── application/
│   ├── __init__.py
│   └── download_service.py
└── infrastructure/
    ├── __init__.py
    ├── browser_manager.py
    └── playwright_adapter.py
```

## Import 对照表

| 旧 import | 新 import |
|-----------|-----------|
| `from packages.common_utils.src.interface.interfaces import ITaskEngine` | `from fr_common_utils.interface.interfaces import ITaskEngine` |
| `from packages.common_utils.src.interface.app_setup import AppSetup` | `from fr_common_utils.interface.app_setup import AppSetup` |
| `from packages.web_automation.src.config import BaseConfig, BrowserConfig` | `from fr_web_automation.config import BaseConfig, BrowserConfig` |
| `from packages.web_automation.src.application.download_service import DownloadService` | `from fr_web_automation.application.download_service import DownloadService` |
| `from packages.web_automation.src.infrastructure.playwright_adapter import OLEDPortalAdapter` | `from fr_web_automation.infrastructure.playwright_adapter import OLEDPortalAdapter` |
| `from packages.web_automation.src.infrastructure.browser_manager import BrowserManager` | `from fr_web_automation.infrastructure.browser_manager import BrowserManager` |
| `from packages.web_automation.src.adapter import WebAutomationAdapter` | `from fr_web_automation.adapter import WebAutomationAdapter` |

## 安装命令

```bash
# 在任何项目中，安装为 editable 模式（改动即时生效）
pip install -e "D:/wzy/Python/packages/common_utils"
pip install -e "D:/wzy/Python/packages/web_automation"

# cell-projects 自身也需要安装
cd D:/wzy/Python/cell-projects
.venv/Scripts/activate
pip install -e packages/common_utils
pip install -e packages/web_automation
```

## pyproject.toml 关键配置

使用 `hatchling` 构建后端，`packages` 指向嵌套后的源码目录：

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/fr_web_automation"]
```

## 日常开发工作流

```
改代码 → 立即生效（editable 模式，无需重装）
    → 在 cell-projects 中测试
    → 在 excel-generator-project 中验证
    → git commit & push
    → 其他项目 pull 即可同步
```

## 2026-05-25 — 合并 ITaskEngine + 迁移到公共路径

- ITaskEngine 从 r-common-utils 移入 r_web_automation.interface，web_automation 不再依赖 common_utils
- common_utils 仍保留供 cell-projects 使用（AppSetup 等）
- 两个包从 cell-projects/packages/ 迁移到 D:/wzy/Python/packages/
