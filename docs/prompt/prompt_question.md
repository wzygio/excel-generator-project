1. 请问为什么要将包的目录结构重构为这种样式，：“““
packages/common_utils/src/fr_common_utils/
├── __init__.py
├── interface/
│   ├── __init__.py
│   ├── interfaces.py      # ITaskEngine
│   └── app_setup.py
├── infrastructure/
│   ├── __init__.py
│   ├── db_manager.py
│   └── logger.py
└── utils/
    ├── __init__.py
    ├── email_utils.py
    ├── html_utils.py
    └── misc.py
”””
既然包名已经被放入了src下，为什么src的上层还要有一层命名，命名规则是什么？

2. 请介绍一下pyproject.toml中的结构。每个部分的作用分别是什么？

3. 将通用包放置于cell-projects中是否合理，是否应该放置于通用路径下？
