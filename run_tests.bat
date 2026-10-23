@echo off
set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"

if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" test_multi_cameras.py
) else (
    python test_multi_cameras.py
)
pause
