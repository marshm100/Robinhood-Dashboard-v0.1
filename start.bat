@echo off
REM ===================================
REM  Robinhood Dashboard Startup Script (start.bat)
REM ===================================
REM Purpose: This script checks for necessary prerequisites (Node.js, npm),
REM          navigates to the project's root directory, and then executes
REM          the main Node.js startup script (start.js) which handles
REM          starting both the backend server and the frontend development server.
REM
REM Order of Operations:
REM 1. Check if Node.js is installed and accessible in the system PATH.
REM 2. Check if npm (Node Package Manager) is installed and accessible.
REM 3. Change the current directory to the directory where this script is located.
REM 4. Execute 'start.js' using Node.js.
REM 5. Keep the console window open after 'start.js' finishes or is stopped.
REM ===================================

echo ===================================
REM Display a user-friendly title
echo  Robinhood Dashboard Startup
echo ===================================
echo.

REM --- Prerequisite Checks ---

REM Check if Node.js is installed
echo Checking for Node.js...
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo ERROR: Node.js is not installed or not in PATH.
  echo Please install Node.js from https://nodejs.org/
  echo.
  pause
  exit /b 1
)
echo Node.js found.

REM Check if npm is installed
echo Checking for npm...
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo ERROR: npm is not installed or not in PATH.
  echo Please ensure npm is properly installed with Node.js.
  echo.
  pause
  exit /b 1
)
echo npm found.
echo.

REM --- Execution ---

echo Starting Robinhood Dashboard...
REM Change directory to the script's location (%~dp0 expands to the drive and path of the batch file)
REM This ensures that relative paths within the Node.js scripts work correctly.
cd %~dp0
echo Changed directory to: %cd%

REM Execute the main startup script using Node.js
REM 'start.js' is responsible for installing dependencies (if needed),
REM starting the backend server, and starting the frontend development server.
node start.js

REM --- Cleanup / User Interaction ---

REM If we get here, the Node.js process ('start.js' and its child processes) has ended.
REM This might happen if the user manually stops the servers (e.g., Ctrl+C in the terminal)
REM or if there was an unrecoverable error in 'start.js'.
echo.
echo Application has stopped.
REM Keep the window open so the user can see any final messages or errors.
REM Pressing any key will close the window.
echo Press any key to exit.
pause 