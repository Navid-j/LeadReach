@echo off
REM ============================================================
REM  LeadReach Updater - for END USERS
REM  Downloads the latest version from GitHub Releases and
REM  replaces the local exe. No git and no Python needed - only
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
set "TMP=leadreach_update_tmp.exe"
set "URL=https://github.com/Navid-j/LeadReach/releases/latest/download/google_100_tabs.exe"
set "VER_URL=https://github.com/Navid-j/LeadReach/releases/latest/download/latest_version.txt"

echo ==========================================
echo   LeadReach Updater
echo ==========================================

if exist "%EXE%" goto :exe_ok
echo [ERROR] %EXE% not found in this folder.
echo         Put this file next to %EXE% and try again.
pause
exit /b 1
:exe_ok

REM -- the exe must be closed, otherwise Windows locks the file --
tasklist /fi "imagename eq %EXE%" 2>nul | find /i "%EXE%" >nul
if errorlevel 1 goto :app_closed
echo [ERROR] The app is still running. Close it first, then run the updater again.
pause
exit /b 1
:app_closed

where curl >nul 2>nul
if not errorlevel 1 goto :curl_ok
echo [ERROR] curl was not found. Windows 10 or newer has it built in.
pause
exit /b 1
:curl_ok

REM -- show which version is the latest on GitHub --
curl -sL --fail --max-time 30 -o latest_version.txt "%VER_URL%"
if exist latest_version.txt set /p LATEST_TAG=<latest_version.txt
if exist latest_version.txt del latest_version.txt
if defined LATEST_TAG echo Latest version on GitHub: %LATEST_TAG%
echo.

echo Downloading the latest version...
curl -L --fail --silent --show-error --max-time 180 -o "%TMP%" "%URL%"
if errorlevel 1 goto :download_failed

REM -- sanity check: a real exe is about 20 MB, so reject tiny files --
for %%A in ("%TMP%") do set "SIZE=%%~zA"
if defined SIZE if %SIZE% GEQ 1000000 goto :size_ok
echo [ERROR] The downloaded file looks wrong or is too small.
echo         Probably no release has been uploaded yet.
del "%TMP%" 2>nul
pause
exit /b 1
:size_ok

echo Replacing the old version...
move /y "%TMP%" "%EXE%" >nul
if errorlevel 1 goto :move_failed

echo.
echo [OK] Updated! You are now on the latest version.
pause
exit /b 0

:download_failed
echo.
echo [ERROR] Download failed. Possible reasons:
echo         - No internet connection
echo         - The developer has not uploaded the new exe to GitHub
echo           Releases yet. Check the release page of the repo.
del "%TMP%" 2>nul
pause
exit /b 1

:move_failed
echo [ERROR] Could not replace %EXE%. Close the app and try again.
del "%TMP%" 2>nul
pause
exit /b 1
