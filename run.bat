@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

rem ============================================================================
rem  SD-Scripts GUI - start the desktop window
rem  Uses the venv created by install.bat directly (no "uv run"), so it works
rem  offline. Set NO_PAUSE=1 to never wait for a key after an error.
rem ============================================================================

setlocal EnableDelayedExpansion
set "IS_DC="
rem Strip the quotes first: Explorer launches cmd.exe /c ""script" " and unbalanced quotes break the if.
set "CL=!cmdcmdline:"=!"
if /i not "!CL:/c =!"=="!CL!" set "IS_DC=1"
endlocal & set "DOUBLE_CLICKED=%IS_DC%"

if exist "backend\.venv\Scripts\python.exe" goto :start
echo.
echo [x] The backend environment was not found.
echo     Run install.bat first, then start run.bat again.
set "RC=1"
goto :finish

:start
cd /d "%~dp0backend"
".venv\Scripts\python.exe" -m app.desktop
set "RC=%errorlevel%"
if not "%RC%"=="0" echo. & echo [x] SD-Scripts GUI exited with code %RC%. If the window never opened, try run-browser.bat.

:finish
if not "%RC%"=="0" if defined DOUBLE_CLICKED if not defined NO_PAUSE pause
exit /b %RC%
