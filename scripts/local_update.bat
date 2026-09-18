@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

python scripts\local_update.py %*
if errorlevel 1 (
  echo.
  echo 同步失败，请看上面的提示。
  if /i not "%~1"=="--auto" pause
  exit /b 1
)

if /i not "%~1"=="--auto" (
  echo.
  pause
)
