@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

rem ============================================================================
rem  SD-Scripts GUI - update a git clone (safe to re-run)
rem
rem    [1/5] checks git, pnpm and that nothing runs from this folder
rem    [2/5] git pull --ff-only of this repository
rem    [3/5] install.bat with UPDATE=1: git pull of sd-scripts, then PyTorch,
rem          the sd-scripts requirements and the backend environment
rem    [4/5] builds the frontend again into backend\web
rem    [5/5] deletes the HTTP cache of the desktop window (WebView2), so it
rem          loads the new frontend. Local Storage (theme, language, drafts) stays.
rem
rem  Only for a git clone. The release zip has no git metadata: download the new
rem  zip instead (docs\en\install-windows.md, section Update).
rem  The install.bat overrides (SD_SCRIPTS_REF, TORCH_INDEX_URL, ...) apply too,
rem  and SD_SCRIPTS_GUI_DATA_ROOT is honoured for the cache folder.
rem    NO_PAUSE=1   never wait for a key at the end
rem ============================================================================

rem Pause at the end only when the script was double-clicked from Explorer.
setlocal EnableDelayedExpansion
set "IS_DC="
rem Strip the quotes first: Explorer launches cmd.exe /c ""script" " and unbalanced quotes break the if.
set "CL=!cmdcmdline:"=!"
if /i not "!CL:/c =!"=="!CL!" set "IS_DC=1"
endlocal & set "DOUBLE_CLICKED=%IS_DC%"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

rem Internal entry point: steps 3 to 5, run by the freshly pulled update.bat.
rem Keep this name and label: older copies of update.bat hand off with it.
if /i "%~1"=="--after-pull" goto :after_pull

set "APP_VERSION=unknown"
if exist "VERSION" set /p APP_VERSION=<"VERSION"
echo.
echo SD-Scripts GUI %APP_VERSION% - updater
echo.

call :preflight
if errorlevel 1 goto :stop

echo.
echo [2/5] Updating SD-Scripts GUI with git pull --ff-only
rem git pull can rewrite this file while it runs, and cmd.exe reads a running
rem batch file line by line at a byte offset. So the pull and the hand-off to
rem the pulled update.bat (started without "call", so this copy never resumes)
rem stay on ONE line, here at the top level and never inside a "call :label".
git -C "%ROOT%" pull --ff-only && "%ROOT%\update.bat" --after-pull
rem Only reached when git pull failed, and then this file is unchanged.
call :fail_pull

:stop
set "RC=1"
goto :finish

:after_pull
call :update_rest
set "RC=%errorlevel%"

:finish
echo.
if "%RC%"=="0" (echo Done.) else (echo Update failed with exit code %RC%.)
if defined DOUBLE_CLICKED if not defined CI if not defined NO_PAUSE pause
exit /b %RC%


rem ---- [1/5] checks, before anything is changed -------------------------------
:preflight
echo [1/5] Checking the install folder
echo     Install folder : "%ROOT%"
where git >nul 2>nul
if errorlevel 1 goto :fail_nogit
if not exist "%ROOT%\.git" goto :fail_notclone
for /f "delims=" %%B in ('git -C "%ROOT%" rev-parse --abbrev-ref HEAD 2^>nul') do echo     Branch         : %%B
where pnpm >nul 2>nul
if errorlevel 1 goto :fail_nopnpm
if not exist "%ROOT%\frontend\package.json" goto :fail_nopnpm
echo     Looking for SD-Scripts GUI or training processes started from this folder ...
rem Stops for anything run from sd-scripts\venv (training, the schema dump) and
rem for the app run from backend\.venv, recognised by app.desktop (run.bat) or
rem app.main (run-browser.bat, uvicorn) in its command line; one whose command
rem line cannot be read counts as the app. Updating an environment under such a
rem process fails on locked files or breaks the run. Other backend\.venv
rem processes, such as the Python tools of an editor, do not stop the update.
rem The venv python.exe is only a launcher (its child runs from the base Python),
rem so the launcher is the process that shows the venv path.
set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_EXE%" set "PS_EXE=powershell.exe"
set "SDGUI_UPDATE_ROOT=%ROOT%"
"%PS_EXE%" -NoLogo -NoProfile -NonInteractive -Command "$r = $env:SDGUI_UPDATE_ROOT.TrimEnd('\') + '\'; $c = [StringComparison]::OrdinalIgnoreCase; $a = $r + 'backend\.venv\'; $b = $r + 'sd-scripts\venv\'; $found = @(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop | Where-Object { $e = $_.ExecutablePath; $e -and ($e.StartsWith($b, $c) -or ($e.StartsWith($a, $c) -and (-not $_.CommandLine -or $_.CommandLine -match '\bapp\.(desktop|main)\b'))) }); foreach ($p in $found) { Write-Host ('      PID ' + $p.ProcessId + '  ' + $p.ExecutablePath) }; if ($found.Count -gt 0) { exit 3 }; exit 0"
set "PS_RC=%errorlevel%"
if "%PS_RC%"=="3" goto :fail_running
if "%PS_RC%"=="0" exit /b 0
echo     [!] Could not check for running processes. Make sure SD-Scripts GUI is closed
echo         and no training is running.
exit /b 0


rem ---- [3/5] to [5/5], run by the freshly pulled update.bat --------------------
:update_rest
set "APP_VERSION=unknown"
if exist "VERSION" set /p APP_VERSION=<"VERSION"
echo     SD-Scripts GUI is now at version %APP_VERSION%.

echo.
echo [3/5] Updating sd-scripts and the environments (install.bat with UPDATE=1)
setlocal
set "UPDATE=1"
set "NO_PAUSE=1"
call "%ROOT%\install.bat"
endlocal & set "STEP_RC=%errorlevel%"
cd /d "%ROOT%"
if not "%STEP_RC%"=="0" goto :fail_install

echo.
echo [4/5] Building the frontend again with pnpm
call pnpm -C frontend install --frozen-lockfile
if errorlevel 1 goto :fail_web
call pnpm -C frontend run build
if errorlevel 1 goto :fail_web
if not exist "backend\web\index.html" goto :fail_web

echo.
echo [5/5] Clearing the desktop window cache
set "DATA_ROOT=%ROOT%\backend\data"
if not defined SD_SCRIPTS_GUI_DATA_ROOT goto :data_root_done
rem Like the app: a relative SD_SCRIPTS_GUI_DATA_ROOT is relative to backend\, where run.bat starts it.
pushd "%ROOT%\backend"
for %%I in ("%SD_SCRIPTS_GUI_DATA_ROOT%") do set "DATA_ROOT=%%~fI"
popd
:data_root_done
set "WV_PROFILE=%DATA_ROOT%\webview\EBWebView\Default"
if exist "%WV_PROFILE%\" goto :wv_clear
echo     No desktop window profile in "%DATA_ROOT%\webview" - skipping.
goto :wv_done
:wv_clear
rem Only the HTTP cache (where a stale index.html lives) and the compiled-script
rem cache. Local Storage, cookies and preferences stay.
if exist "%WV_PROFILE%\Cache\" rmdir /s /q "%WV_PROFILE%\Cache"
if exist "%WV_PROFILE%\Code Cache\" rmdir /s /q "%WV_PROFILE%\Code Cache"
if exist "%WV_PROFILE%\Cache\" goto :fail_cache
if exist "%WV_PROFILE%\Code Cache\" goto :fail_cache
echo     Cleared the cache in "%WV_PROFILE%"
:wv_done

echo.
echo ============================================================================
echo  Update complete.
echo.
echo    run.bat           open SD-Scripts GUI in its own desktop window
echo    run-browser.bat   open it in your web browser instead. If the browser still
echo                      shows the old version, reload the page with Ctrl+F5.
echo.
echo  If sd-scripts changed, the app rebuilds its argument schema in the background
echo  on the next start.
echo ============================================================================
exit /b 0


rem ---- failure messages --------------------------------------------------------
:fail_nogit
echo.
echo [x] Step 1/5 failed: git was not found.
echo     update.bat updates a git clone. Install git from https://git-scm.com/download/win,
echo     open a new window and run update.bat again. If you installed from the release zip,
echo     download the new zip instead: see docs\en\install-windows.md, section Update.
exit /b 1

:fail_notclone
echo.
echo [x] Step 1/5 failed: this folder is not a git clone, so update.bat cannot update it.
echo     If you installed from the release zip, download the new zip from
echo     https://github.com/vjumpkung/vjump-sd-scripts-gui/releases, extract it over this
echo     folder and run install.bat again. See docs\en\install-windows.md, section Update.
exit /b 1

:fail_nopnpm
echo.
echo [x] Step 1/5 failed: pnpm or the frontend sources were not found, so the frontend cannot be built.
echo     Install Node.js and pnpm from https://pnpm.io/installation, open a new window and
echo     run update.bat again.
exit /b 1

:fail_running
echo.
echo [x] Step 1/5 failed: SD-Scripts GUI or a training run is still running from this folder.
echo     The processes are listed above. Wait for the training to finish, close the SD-Scripts GUI
echo     window or press Ctrl+C in the run-browser.bat console, then run update.bat again.
echo     Nothing has been changed.
exit /b 1

:fail_pull
echo.
echo [x] Step 2/5 failed: git pull --ff-only returned an error. Your files were not changed.
echo     Scroll up for the message from git. Common causes: no internet connection, local
echo     changes to files that the update also changes, local commits that diverged from the
echo     remote, or a branch without an upstream. "git status" shows your changes: commit,
echo     stash or undo them, then run update.bat again.
exit /b 1

:fail_install
echo.
echo [x] Step 3/5 failed: install.bat stopped with exit code %STEP_RC%. Its message is above.
echo     SD-Scripts GUI itself is already updated. Fix the cause and run update.bat again.
exit /b 1

:fail_web
echo.
echo [x] Step 4/5 failed: building the frontend returned an error.
echo     Scroll up for the error, fix it and run update.bat again.
exit /b 1

:fail_cache
echo.
echo [x] Step 5/5 failed: the desktop window cache could not be deleted, most likely because an
echo     SD-Scripts GUI window is still open. Everything else is updated. Close every SD-Scripts
echo     GUI window and run update.bat again, or delete this folder by hand:
echo     "%WV_PROFILE%\Cache"
exit /b 1
