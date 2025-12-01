@echo off
TITLE Excel Generator App (Port 8502)
ECHO ========================================================
ECHO       Starting Excel Generator Project...
ECHO       (Root Directory Execution + PYTHONPATH)
ECHO ========================================================

REM 1. 切换到项目根目录
D:
cd "D:\wzy\Python\excel-generator-project"
ECHO [INFO] Current directory: %cd%

REM ========================================================
REM [关键修改 1] 激活虚拟环境
REM 根据你原脚本中的 "..\excel-generator-project\Scripts\python.exe" 推断，
REM 你的虚拟环境文件夹名字就叫 "excel-generator-project"
REM ========================================================
IF EXIST "excel-generator-project\Scripts\activate.bat" (
    call "excel-generator-project\Scripts\activate.bat"
    ECHO [INFO] Virtual Environment activated.
) ELSE (
    ECHO [WARNING] Virtual environment not found at expected path.
    ECHO [INFO] Trying to run with system python...
)

REM ========================================================
REM [关键修改 2] 设置 PYTHONPATH
REM 将 src 加入搜索路径，替代原本的 "pushd src"
REM ========================================================
set PYTHONPATH=%cd%\src;%PYTHONPATH%
ECHO [INFO] PYTHONPATH set to include src directory.

REM ========================================================
REM [关键修改 3] 启动 Streamlit 服务
REM 1. 使用 python -m streamlit (标准启动方式)
REM 2. 路径指向 src 下的 app.py
REM ========================================================
ECHO [INFO] Starting Streamlit App on Port 8502...

python -m streamlit run src\excel_generator_project\app\app.py --server.port 8502

REM 保持窗口开启，以便查看报错日志
pause