@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

rem ============================================================================
rem  SD-Scripts GUI - Windows installer (idempotent, safe to re-run)
rem
rem  Optional overrides (set before running, e.g. "set UPDATE=1 && install.bat"):
rem    SD_SCRIPTS_REPO, SD_SCRIPTS_REF   which sd-scripts fork/branch to use
rem    TORCH_VERSION, TORCHVISION_VERSION, TORCH_INDEX_URL
rem    UPDATE=1                          git pull an existing sd-scripts clone
rem    NO_PAUSE=1                        never wait for a key at the end
rem
rem  Plain batch only: no downloaded scripts are piped into a shell.
rem ============================================================================

rem Pause at the end only when the script was double-clicked from Explorer.
setlocal EnableDelayedExpansion
set "IS_DC="
rem Strip the quotes first: Explorer launches cmd.exe /c ""script" " and unbalanced quotes break the if.
set "CL=!cmdcmdline:"=!"
if /i not "!CL:/c =!"=="!CL!" set "IS_DC=1"
endlocal & set "DOUBLE_CLICKED=%IS_DC%"

call :main
set "RC=%errorlevel%"

echo.
if "%RC%"=="0" (echo Done.) else (echo Installation failed with exit code %RC%.)
if defined DOUBLE_CLICKED if not defined CI if not defined NO_PAUSE pause
exit /b %RC%


rem ----------------------------------------------------------------------------
:main
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "APP_VERSION=unknown"
if exist "VERSION" set /p APP_VERSION=<"VERSION"

echo.
echo SD-Scripts GUI %APP_VERSION% - installer
echo.
echo [1/9] Configuration
if not defined SD_SCRIPTS_REPO set "SD_SCRIPTS_REPO=https://github.com/vjumpkung/sd-scripts.git"
if not defined SD_SCRIPTS_REF set "SD_SCRIPTS_REF=feat/vjump"
if not defined TORCH_VERSION set "TORCH_VERSION=2.8.0"
if not defined TORCHVISION_VERSION set "TORCHVISION_VERSION=0.23.0"
if not defined TORCH_INDEX_URL set "TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128"
echo     Install folder : "%ROOT%"
echo     sd-scripts     : "%SD_SCRIPTS_REPO%" branch "%SD_SCRIPTS_REF%"
echo     torch          : "%TORCH_VERSION%" and torchvision "%TORCHVISION_VERSION%"
echo     torch index    : "%TORCH_INDEX_URL%"

rem ---- [2/9] uv ---------------------------------------------------------------
echo.
echo [2/9] Looking for uv
call :find_uv
if defined UV goto :uv_ok
where winget >nul 2>nul
if errorlevel 1 goto :fail_uv
echo     uv was not found. Installing it with winget ...
winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
rem winget does not refresh PATH in this shell, so look in the known locations.
call :find_uv
if not defined UV goto :fail_uv
:uv_ok
echo     Using "%UV%"

rem ---- [3/9] Python 3.12 -------------------------------------------------------
echo.
echo [3/9] Installing Python 3.12 (managed by uv)
"%UV%" python install 3.12
if errorlevel 1 goto :fail_python

rem ---- [4/9] sd-scripts --------------------------------------------------------
echo.
echo [4/9] Getting sd-scripts
if exist "sd-scripts\.git" goto :sd_git
if exist "sd-scripts\requirements.txt" goto :sd_nogit
where git >nul 2>nul
if errorlevel 1 goto :sd_zip
echo     Cloning "%SD_SCRIPTS_REPO%" branch "%SD_SCRIPTS_REF%" ...
git clone --branch "%SD_SCRIPTS_REF%" "%SD_SCRIPTS_REPO%" "sd-scripts"
if errorlevel 1 goto :fail_clone
goto :sd_done

:sd_git
if "%UPDATE%"=="1" goto :sd_update
echo     sd-scripts is already present - skipping. Set UPDATE=1 to pull the latest commit.
goto :sd_done

:sd_update
echo     Updating sd-scripts with git pull --ff-only ...
git -C "sd-scripts" pull --ff-only
if errorlevel 1 goto :fail_update
goto :sd_done

:sd_nogit
echo     sd-scripts is already present - skipping.
echo     It has no git metadata, so UPDATE=1 has no effect. Delete the sd-scripts folder to download it again.
goto :sd_done

:sd_zip
echo     git was not found - downloading a zip archive instead.
echo     NOTE: schema commit detection will be unavailable for this copy of sd-scripts.
set "DL_DIR=%ROOT%\.sd-scripts-dl"
set "REPO_BASE=%SD_SCRIPTS_REPO:.git=%"
set "ZIP_URL=%REPO_BASE:https://github.com/=https://codeload.github.com/%/zip/refs/heads/%SD_SCRIPTS_REF%"
set "TAR=%SystemRoot%\System32\tar.exe"
if not exist "%TAR%" set "TAR=tar"
if exist "%DL_DIR%" rmdir /s /q "%DL_DIR%"
mkdir "%DL_DIR%"
echo     Downloading "%ZIP_URL%"
curl.exe -L --fail -o "%DL_DIR%\sd-scripts.zip" "%ZIP_URL%"
if errorlevel 1 goto :fail_download
"%TAR%" -xf "%DL_DIR%\sd-scripts.zip" -C "%DL_DIR%"
if errorlevel 1 goto :fail_extract
del /q "%DL_DIR%\sd-scripts.zip"
rem Remove an empty leftover folder so the move below renames instead of nesting.
rmdir "sd-scripts" 2>nul
for /d %%D in ("%DL_DIR%\*") do move "%%~D" "sd-scripts" >nul
rmdir /s /q "%DL_DIR%"
if not exist "sd-scripts\requirements.txt" goto :fail_extract

:sd_done

rem ---- [5/9] sd-scripts virtual environment ------------------------------------
echo.
echo [5/9] Creating the sd-scripts virtual environment (Python 3.12)
if exist "sd-scripts\venv\Scripts\python.exe" goto :venv_present
"%UV%" venv --python 3.12 "sd-scripts\venv"
if errorlevel 1 goto :fail_venv
goto :venv_done
:venv_present
echo     sd-scripts\venv already exists - reusing it.
:venv_done

rem ---- [6/9] torch + requirements ----------------------------------------------
echo.
echo [6/9] Installing PyTorch and the sd-scripts requirements (several GB on the first run)
pushd "sd-scripts"
"%UV%" pip install --python "venv\Scripts\python.exe" "torch==%TORCH_VERSION%" "torchvision==%TORCHVISION_VERSION%" --index-url "%TORCH_INDEX_URL%"
if errorlevel 1 goto :fail_torch
"%UV%" pip install --python "venv\Scripts\python.exe" -r requirements.txt
if errorlevel 1 goto :fail_requirements
echo     Checking that torch is a CUDA build ...
"venv\Scripts\python.exe" -c "import torch,sys; v=torch.__version__; print(v); sys.exit(0 if '+cu' in v else 1)"
if errorlevel 1 goto :fail_cuda
popd

rem ---- [7/9] backend -----------------------------------------------------------
echo.
echo [7/9] Installing the backend (including the desktop window support)
"%UV%" sync --project backend --extra desktop --no-dev --inexact
if errorlevel 1 goto :fail_backend

rem ---- [8/9] frontend assets ---------------------------------------------------
echo.
echo [8/9] Checking the frontend assets
if exist "backend\web\index.html" goto :web_ok
where pnpm >nul 2>nul
if errorlevel 1 goto :fail_nopnpm
if not exist "frontend\package.json" goto :fail_nopnpm
echo     Building the frontend with pnpm ...
call pnpm -C frontend install --frozen-lockfile
if errorlevel 1 goto :fail_web
call pnpm -C frontend run build
if errorlevel 1 goto :fail_web
if not exist "backend\web\index.html" goto :fail_web
goto :web_done
:web_ok
echo     backend\web is already built - skipping.
:web_done

rem ---- [9/9] workspace ---------------------------------------------------------
echo.
echo [9/9] Preparing the workspace folder
if not exist "workspace" mkdir "workspace"
echo     "%ROOT%\workspace"

echo.
echo ============================================================================
echo  Installation complete.
echo.
echo    run.bat           open SD-Scripts GUI in its own desktop window
echo    run-browser.bat   open SD-Scripts GUI in your web browser instead
echo ============================================================================
exit /b 0


rem ---- failure messages --------------------------------------------------------
:fail_uv
echo.
echo [x] uv is required but was not found, and it could not be installed automatically.
echo     Install it from https://docs.astral.sh/uv/getting-started/installation/
echo     for example with: winget install --id astral-sh.uv -e
echo     Then close this window, open a new one and run install.bat again.
exit /b 1

:fail_python
echo.
echo [x] Step 3/9 failed: "uv python install 3.12" returned an error.
echo     Check your internet connection and run install.bat again.
exit /b 1

:fail_clone
echo.
echo [x] Step 4/9 failed: git clone returned an error.
echo     Check your internet connection, SD_SCRIPTS_REPO and SD_SCRIPTS_REF, and that the "sd-scripts" folder is empty or missing.
exit /b 1

:fail_update
echo.
echo [x] Step 4/9 failed: git pull --ff-only returned an error.
echo     The sd-scripts folder has local changes or diverged history. Resolve it manually with git, or delete the folder.
exit /b 1

:fail_download
echo.
echo [x] Step 4/9 failed: the sd-scripts archive could not be downloaded.
echo     Check your internet connection, SD_SCRIPTS_REPO and SD_SCRIPTS_REF. Alternatively install git and run install.bat again.
if exist "%DL_DIR%" rmdir /s /q "%DL_DIR%"
exit /b 1

:fail_extract
echo.
echo [x] Step 4/9 failed: the sd-scripts archive could not be extracted.
echo     Windows 10 1803 or newer is required for tar.exe. Alternatively install git and run install.bat again.
if exist "%DL_DIR%" rmdir /s /q "%DL_DIR%"
exit /b 1

:fail_venv
echo.
echo [x] Step 5/9 failed: could not create sd-scripts\venv.
echo     Delete the sd-scripts\venv folder if it is partially created and run install.bat again.
exit /b 1

:fail_torch
popd
echo.
echo [x] Step 6/9 failed: PyTorch "%TORCH_VERSION%" / torchvision "%TORCHVISION_VERSION%" could not be installed from
echo     "%TORCH_INDEX_URL%"
echo     Check your internet connection and free disk space, or set TORCH_VERSION, TORCHVISION_VERSION and TORCH_INDEX_URL.
exit /b 1

:fail_requirements
popd
echo.
echo [x] Step 6/9 failed: installing the sd-scripts requirements returned an error.
echo     Scroll up for the package that failed, fix the cause and run install.bat again.
exit /b 1

:fail_cuda
popd
echo.
echo [x] Step 6/9 failed: the installed torch is not a CUDA build, which means a CPU build was installed.
echo     Another package probably replaced it. Set TORCH_INDEX_URL to the index matching your GPU driver
echo     (default https://download.pytorch.org/whl/cu128), delete sd-scripts\venv and run install.bat again.
exit /b 1

:fail_backend
echo.
echo [x] Step 7/9 failed: "uv sync" for the backend returned an error.
echo     Check your internet connection and run install.bat again.
exit /b 1

:fail_nopnpm
echo.
echo [x] Step 8/9 failed: the frontend has not been built and pnpm or the frontend sources are missing.
echo     Either download the release zip, which already contains the built frontend,
echo     or install Node.js and pnpm (https://pnpm.io/installation) and run install.bat again.
exit /b 1

:fail_web
echo.
echo [x] Step 8/9 failed: building the frontend returned an error.
echo     Scroll up for the error, fix it and run install.bat again.
exit /b 1


rem ---- helpers -----------------------------------------------------------------
:find_uv
set "UV="
for /f "delims=" %%I in ('where uv.exe 2^>nul') do if not defined UV set "UV=%%I"
if not defined UV if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe" set "UV=%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
exit /b 0
