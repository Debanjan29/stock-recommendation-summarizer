@echo off
setlocal

set PYTHON_CMD=python
if exist ".\.venv\Scripts\python.exe" (
    set "PYTHON_CMD=.\.venv\Scripts\python.exe"
)

echo ============================================================
echo  STARTING INDIAN STOCK EXTRACTOR WEB APP
echo  Opening at http://127.0.0.1:8000
echo ============================================================

%PYTHON_CMD% -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
pause
