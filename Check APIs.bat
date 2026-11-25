@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (python check_apis.py) else (py check_apis.py)
pause
