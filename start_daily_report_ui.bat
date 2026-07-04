@echo off
setlocal

set "PROJECT_DIR=D:\wzy\Python\excel-generator-project"
set "PORT=8502"
set "LOG_DIR=output\logs"
set "LOG_FILE=%LOG_DIR%\daily_report_ui_start.log"

cd /d "%PROJECT_DIR%"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "output\artifacts\reports\generated" mkdir "output\artifacts\reports\generated"

echo [%date% %time%] Starting daily report UI on port %PORT%.>> "%LOG_FILE%"

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    echo [%date% %time%] Stopping process on port %PORT%: %%a>> "%LOG_FILE%"
    taskkill /PID %%a /F >> "%LOG_FILE%" 2>&1
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%cd%\src;%cd%;%PYTHONPATH%"
set "DAILY_REPORT_GENERATOR_ROOT=C:\Users\V0141351\.agents\skills\daily-report-generator"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

python -m streamlit run app\daily_report_app.py --server.port %PORT% --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false >> "%LOG_FILE%" 2>&1

endlocal
