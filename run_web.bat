@echo off
set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"

if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" web_app.py
) else (
    python web_app.py
)
pause
