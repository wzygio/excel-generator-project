REM ========================================================
REM 0. 自动查杀旧进程。防止进程堆积，确保每次启动都是最新的单一实例
REM ========================================================
ECHO [INFO] Checking for existing process on port 8502...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8502" ^| find "LISTENING"') do (
    ECHO [INFO] Killing old process PID: %%a
    taskkill /f /pid %%a >nul 2>&1
)

REM ========================================================
REM 1. 设置环境变量
REM ========================================================
D:
cd "D:\wzy\Python\excel-generator-project"
set PYTHONPATH=%cd%\src;%PYTHONPATH%


REM ========================================================
REM 2. 激活虚拟环境
REM ========================================================
IF EXIST "excel-generator-project\Scripts\activate.bat" (
    call "excel-generator-project\Scripts\activate.bat"
)

REM ========================================================
REM 3. 启动 Streamlit (使用 pythonw)
REM ========================================================
ECHO [INFO] Starting new instance...
start "" pythonw -m streamlit run src\excel_generator_project\app\app.py --server.port 8502 --server.headless true

REM ========================================================
REM 4. 退出
REM ========================================================
exit