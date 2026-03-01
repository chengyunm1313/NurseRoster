@echo off
setlocal

set ROOT_DIR=%~dp0
set VENV_DIR=%ROOT_DIR%.venv
set PORT=8765

where py >nul 2>nul
if %errorlevel%==0 (
  set PYTHON_CMD=py -3
) else (
  set PYTHON_CMD=python
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
  %PYTHON_CMD% -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r "%ROOT_DIR%requirements.txt"
start "" "http://127.0.0.1:%PORT%"
python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

endlocal
