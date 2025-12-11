@echo off

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist "venv\bin\activate" (
    call venv\bin\activate
)

REM Start the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
