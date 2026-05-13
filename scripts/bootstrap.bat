@echo off
setlocal EnableExtensions EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..

echo.
echo === Configo Workspace Bootstrap ===
echo Root: %ROOT%
echo.

where git >nul 2>nul || (
  echo [ERROR] Git is required. Install Git and re-run bootstrap.
  exit /b 1
)

where python >nul 2>nul || (
  echo [ERROR] Python is required. Install Python and re-run bootstrap.
  exit /b 1
)

where node >nul 2>nul || (
  echo [ERROR] Node.js is required. Install Node.js and re-run bootstrap.
  exit /b 1
)

where npm >nul 2>nul || (
  echo [ERROR] npm is required. Install Node.js and re-run bootstrap.
  exit /b 1
)

where opencode >nul 2>nul || (
  echo Installing OpenCode...
  call npm install -g opencode-ai
)

where auggie >nul 2>nul || (
  echo Installing Auggie CLI...
  call npm install -g @augmentcode/auggie@latest
)

if not exist "%USERPROFILE%\.config\opencode" mkdir "%USERPROFILE%\.config\opencode"
call npm install superpowers@git+https://github.com/obra/superpowers.git --prefix "%USERPROFILE%\.config\opencode"
call npx -y ctx7 setup --opencode --yes
python "%ROOT%\tools\setup_opencode.py" configure --root "%ROOT%" || exit /b 1

echo.
echo Bootstrap complete.
echo Next steps:
echo   1. Run "auggie login" if this machine is not already authenticated
echo   2. Install the Augment GitHub App and select the Configo repos for remote indexing
echo   3. Open OpenCode and verify both local and remote Augment MCP servers are available
echo   4. Copy Configo-Backend\.env.staging.example to Configo-Backend\.env.staging
echo   5. Fill in staging credentials
echo   6. Run scripts\dev.bat
echo.
