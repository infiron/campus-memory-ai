@echo off
setlocal
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)
call ".venv\Scripts\activate.bat"
if not exist ".env" copy ".env.example" ".env" >nul
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
echo.
echo Starting Campus Memory AI at http://127.0.0.1:8000
echo Press Ctrl+C to stop the server.
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
goto :eof
:error
echo Setup failed. Please check that Python 3.11+ is installed and try again.
pause
exit /b 1
