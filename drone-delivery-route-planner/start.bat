@echo off
REM Double-click this file (Windows) to set up and start the website.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py start.py %*) else (python start.py %*)
echo.
pause
