@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

rem ============================================================================
rem  SD-Scripts GUI - start the server and open it in your web browser
rem  Use this when the desktop window does not work (for example, WebView2 is
rem  missing). Set SD_SCRIPTS_GUI_PORT to change the port (default 8000).
rem  Set NO_PAUSE=1 to never wait for a key after an error.
rem ============================================================================

rem Internal entry point: the background helper started below calls this script
rem again with --wait-and-open <port>.
if /i "%~1"=="--wait-and-open" goto :wait_and_open

setlocal EnableDelayedExpansion
set "IS_DC="
rem Strip the quotes first: Explorer launches cmd.exe /c ""script" " and unbalanced quotes break the if.
set "CL=!cmdcmdline:"=!"
if /i not "!CL:/c =!"=="!CL!" set "IS_DC=1"
endlocal & set "DOUBLE_CLICKED=%IS_DC%"

if exist "backend\.venv\Scripts\python.exe" goto :start
echo.
echo [x] The backend environment was not found.
echo     Run install.bat first, then start run-browser.bat again.
set "RC=1"
goto :finish

:start
if not defined SD_SCRIPTS_GUI_PORT set "SD_SCRIPTS_GUI_PORT=8000"
set "PORT=%SD_SCRIPTS_GUI_PORT%"
set "SD_SCRIPTS_GUI_ALLOWED_HOSTS=127.0.0.1,localhost"
cd /d "%~dp0backend"

echo Starting SD-Scripts GUI on "http://127.0.0.1:%PORT%/"
echo Your browser opens when the server is ready. Press Ctrl+C or close this window to stop.
echo.
start "" /b cmd /c call "%~f0" --wait-and-open "%PORT%"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port "%PORT%" --workers 1 --timeout-graceful-shutdown 5
set "RC=%errorlevel%"
if not "%RC%"=="0" echo. & echo [x] The server exited with code %RC%.

:finish
if not "%RC%"=="0" if defined DOUBLE_CLICKED if not defined NO_PAUSE pause
exit /b %RC%


rem ---- background helper: poll the server, then open the browser ---------------
:wait_and_open
set "PORT=%~2"
for /l %%I in (1,1,60) do (
  curl.exe -s -o nul "http://127.0.0.1:%PORT%/api/system/status" && goto :open_browser
  ping -n 2 127.0.0.1 >nul
)
exit /b 1

:open_browser
start "" "http://127.0.0.1:%PORT%/"
exit /b 0
