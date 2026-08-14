@echo off
REM ============================================================
REM  LeadReach Updater — for END USERS
REM  Downloads the latest version from GitHub Releases and
REM  replaces the local exe. No git and no Python needed — only
REM  curl, which is built into Windows 10 and newer.
REM
REM  HOW TO USE:
REM  1. Put this file in the SAME folder as google_100_tabs.exe
REM  2. Double-click it
REM  3. Wait for "[OK] Updated!" then close the window
REM ============================================================
setlocal
cd /d "%~dp0"

set "EXE=google_100_tabs.exe"
set "TMP=google_100_tabs.new.exe"

REM ====== WHERE TO DOWNLOAD THE NEW EXE FROM ======
REM Paste the direct download link of the new exe below.
REM The link must download the file directly (no login page).
REM
REM Examples:
REM   GitHub Releases (always gets the newest release):
REM     https://github.com/USER/REPO/releases/latest/download/google_100_tabs.exe
REM   Google Drive (file shared with "anyone with link"):
REM     https://drive.google.com/uc?export=download&id=FILE_ID
REM   Dropbox:
REM     https://www.dropbox.com/s/FILE_ID/google_100_tabs.exe?dl=1
set "URL=https://github.com/Navid-j/LeadReach/releases/latest/download/google_100_tabs.exe"

echo ==========================================
echo   LeadReach Updater
echo ==========================================

if not exist "%EXE%" (
    echo [ERROR] %EXE% not found in this folder.
    echo         Put this file next to %EXE% and try again.
    pause
    exit /b 1
)

REM -- the exe must be closed, otherwise Windows locks the file --
tasklist /fi "imagename eq %EXE%" 2>nul | find /i "%EXE%" >nul
if not errorlevel 1 (
    echo [ERROR] The app is still running. Close it first, then run the updater again.
    pause
    exit /b 1
)

where curl >nul 2>nul
if errorlevel 1 (
    echo [ERROR] curl was not found. Windows 10 or newer has it built in.
    pause
    exit /b 1
)

echo Downloading the latest version...
curl -L --fail --silent --show-error -o "%TMP%" "%URL%"
if errorlevel 1 (
    echo.
    echo [ERROR] Download failed. Possible reasons:
    echo         - No internet connection
    echo         - The developer has not uploaded the new exe to GitHub
    echo           Releases yet (see the release page of the repo)
    del "%TMP%" 2>nul
    pause
    exit /b 1
)

REM -- sanity check: a real exe is about 20 MB --
for %%A in ("%TMP%") do set "SIZE=%%~zA"
if %SIZE% LSS 1000000 (
    echo [ERROR] The downloaded file looks wrong (only %SIZE% bytes).
    echo         Probably no release has been uploaded yet.
    del "%TMP%" 2>nul
    pause
    exit /b 1
)

echo Replacing the old version...
move /y "%TMP%" "%EXE%" >nul
if errorlevel 1 (
    echo [ERROR] Could not replace %EXE%. Close the app and try again.
    del "%TMP%" 2>nul
    pause
    exit /b 1
)

echo.
echo [OK] Updated! You are now on the latest version.
pause
