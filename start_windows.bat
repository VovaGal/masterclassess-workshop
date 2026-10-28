@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Run setup_windows.bat first.
 pause
 exit /b 1
)
echo Open http://127.0.0.1:8000 in your browser.
echo Leave this window open. Ctrl+C stops the server.
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
pause
