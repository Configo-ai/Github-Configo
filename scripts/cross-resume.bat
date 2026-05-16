@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
set "COMMAND=%~1"
if "%COMMAND%"=="" set "COMMAND=list"

if /I "%COMMAND%"=="list" (
  python "%ROOT%\tools\session_runtime.py" list --root "%ROOT%" --cwd "%CD%"
  exit /b %errorlevel%
)

if /I "%COMMAND%"=="use" (
  if "%~2"=="" (
    echo Usage: scripts\cross-resume.bat use ^<workspace_conversation_id^>
    exit /b 1
  )
  python "%ROOT%\tools\session_runtime.py" activate --root "%ROOT%" --cwd "%CD%" --conversation "%~2"
  exit /b %errorlevel%
)

if /I "%COMMAND%"=="claude" (
  goto :claude
)

if /I "%COMMAND%"=="opencode" (
  goto :opencode
)

echo Usage:
echo   scripts\cross-resume.bat
echo   scripts\cross-resume.bat list
echo   scripts\cross-resume.bat use ^<workspace_conversation_id^>
echo   scripts\cross-resume.bat claude ^<workspace_conversation_id^> [claude args...]
echo   scripts\cross-resume.bat opencode ^<workspace_conversation_id^> [opencode args...]
exit /b 1

:claude
if "%~2"=="" (
  echo Usage: scripts\cross-resume.bat claude ^<workspace_conversation_id^> [claude args...]
  exit /b 1
)
set "CONVERSATION=%~2"
shift
shift
python "%ROOT%\tools\workspace_launcher.py" claude --root "%ROOT%" --cwd "%CD%" --conversation "%CONVERSATION%" -- %*
exit /b %errorlevel%

:opencode
if "%~2"=="" (
  echo Usage: scripts\cross-resume.bat opencode ^<workspace_conversation_id^> [opencode args...]
  exit /b 1
)
set "CONVERSATION=%~2"
shift
shift
python "%ROOT%\tools\workspace_launcher.py" opencode --root "%ROOT%" --cwd "%CD%" --conversation "%CONVERSATION%" -- %*
exit /b %errorlevel%
