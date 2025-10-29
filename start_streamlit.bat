@echo off
ECHO Starting Streamlit Report App in the background...

REM 1. 切换到项目所在的盘符 (请根据实际情况修改)
D:

REM 2. 进入项目根目录的绝对路径 (请根据实际情况修改)
cd D:\wzy\Python\excel-generator-project

REM 3. 使用 start /B 命令，并指定完整的Python解释器路径来启动服务
REM    这是最关键的一步
.\excel-generator-project\Scripts\python.exe -m streamlit run app.py --server.headless true --server.port 8502
