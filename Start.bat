@echo off
cd /d "%~dp0"

echo.
echo  PhD Tracker - starting...
echo  Keep this window open. Close it to stop the app.
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    echo Install Python and check "Add python.exe to PATH".
    pause
    exit /b 1
)

python -c "import streamlit, pandas, plotly" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies, please wait...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] pip install failed.
        pause
        exit /b 1
    )
)

echo Opening browser...
start "" "http://localhost:8501"
python -m streamlit run app.py --server.headless true

echo.
echo App stopped.
pause
