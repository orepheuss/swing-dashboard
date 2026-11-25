@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (python rs_ranker.py) else (py rs_ranker.py)
pause
