@echo off
REM ============================================================
REM  LeadReach Updater
REM  Pulls the latest code from git, updates Python dependencies,
REM  and rebuilds dist\google_100_tabs.exe when one is present.
REM
REM  Works from the repo root OR from the dist\ folder (next to
REM  the .exe). Requires git. A rebuild also requires Python +
REM  PyInstaller.
REM ============================================================
setlocal
cd /d "%~dp0"

REM -- locate the git repo (this folder, or the parent if run from dist\) --
if not exist ".git" (
    if exist "..\.git" (
        cd ..
    ) else (
        echo [ERROR] No git repository found here or in the parent folder.
        echo         update.bat must live inside a git clone of LeadReach.
        pause
        exit /b 1
    )
)

echo ==========================================
echo   LeadReach Updater
echo ==========================================
echo Repo : %CD%
echo.

where git >nul 2>nul
if errorlevel 1 (
    echo [ERROR] git was not found. Install it first: https://git-scm.com/
    pause
    exit /b 1
)

echo [1/3] Pulling latest changes from git...
git pull --ff-only
if errorlevel 1 (
    echo.
    echo [ERROR] git pull failed. Possible reasons:
    echo         - You have uncommitted local changes that conflict with upstream.
    echo         - The current branch does not track a remote yet.
    echo         - This folder is not a git clone.
    pause
    exit /b 1
)

echo.
echo [2/3] Updating Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [WARN] Could not install dependencies. Run it manually later:
    echo        python -m pip install -r requirements.txt
)

echo.
echo [3/3] Checking whether the .exe needs a rebuild...
if exist "dist\google_100_tabs.exe" (
    where pyinstaller >nul 2>nul
    if errorlevel 1 (
        echo [INFO] An exe exists but PyInstaller is not installed, so I cannot
        echo        rebuild it. Rebuild manually with:
        echo        python -m pip install pyinstaller
        echo        pyinstaller google_100_tabs.spec
    ) else (
        echo Rebuilding dist\google_100_tabs.exe ... this takes 1-2 minutes.
        pyinstaller google_100_tabs.spec
        if errorlevel 1 (
            echo [WARN] Rebuild failed - check the output above.
        ) else (
            echo [OK] New exe written to dist\google_100_tabs.exe
        )
    )
) else (
    echo [INFO] No exe in dist\ - you are running from source:
    echo        python google_100_tabs.py
)

echo.
echo Done! You are now on the latest version.
pause
