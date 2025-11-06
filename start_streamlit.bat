@echo off
ECHO Starting Streamlit Report App in the background...

REM 1. 切换到项目所在的盘符 (请根据实际情况修改)
D:

REM 2. 进入项目根目录的绝对路径 (请根据实际情况修改)
cd D:\wzy\Python\excel-generator-project

REM 3. [核心修改] 进入 'src' 目录
ECHO [INFO] Changing working directory to 'src'...
pushd src

REM 4. 启动 Streamlit 服务：
..\excel-generator-project\Scripts\python.exe -m streamlit run excel_generator_project\app\app.py --server.port 8502

REM 5. [推荐] 当服务停止后 (例如你按了 Ctrl+C)，退出 'src' 目录
popd