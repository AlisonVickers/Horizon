@echo off
REM Horizon: Heena's backend + Alison's v2 frontend, served together by the API adapter.
cd /d "%~dp0"
where python >nul 2>nul || (echo Python is not installed. Install Python 3.11+ from python.org & pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment - first run only...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
echo Installing packages - first run takes a few minutes...
python -m pip install -q --disable-pip-version-check -r requirements.txt
if not exist "frontend\dist\index.html" (echo frontend\dist is missing. & pause & exit /b 1)
set PORT=8000
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul && set PORT=8001
start "" cmd /c "timeout /t 8 >nul & start http://127.0.0.1:%PORT%/"
echo.
echo Horizon is running at http://127.0.0.1:%PORT%  (close this window to stop)
python -m uvicorn api_adapter.main:app --host 127.0.0.1 --port %PORT%
pause
