@echo off
echo ===================================
echo  Robinhood Dashboard Startup
echo ===================================
echo.

REM Check if Node.js is installed
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo ERROR: Node.js is not installed or not in PATH.
  echo Please install Node.js from https://nodejs.org/
  echo.
  pause
  exit /b 1
)

REM Check if npm is installed
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo ERROR: npm is not installed or not in PATH.
  echo Please ensure npm is properly installed with Node.js.
  echo.
  pause
  exit /b 1
)

echo Starting Robinhood Dashboard...
cd %~dp0
node start.js

REM If we get here, the process has ended
echo.
echo Application has stopped. Press any key to exit.
pause 