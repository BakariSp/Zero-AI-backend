@echo off
REM Batch file to run the learning path export on Windows

echo Running Learning Path Export Script...
echo.

REM Pass all arguments to the PowerShell script
powershell -ExecutionPolicy Bypass -File "%~dp0\run_export.ps1" %*

echo.
echo Script execution completed.

REM Pause to keep the window open if it was launched by double-clicking
if not defined PROMPT pause 