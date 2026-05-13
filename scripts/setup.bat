@echo off
setlocal EnableDelayedExpansion

echo.
echo   Configo Workspace Setup
echo   %time%
echo.

set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..

cd /d "%ROOT%"

where git >nul 2>nul
if errorlevel 1 (
    echo   [ERROR] Git is required
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo   [ERROR] Python is required
    exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
    echo   [ERROR] Node.js is required
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo   [ERROR] npm is required
    exit /b 1
)

call :ensure_repo "Configo-Backend" "https://github.com/Configo-ai/Configo-Backend.git"
call :ensure_repo "Configo-AI-Worker" "https://github.com/Configo-ai/Configo-AI-Worker.git"
call :ensure_repo "Configo-Frontend" "https://github.com/Configo-ai/Configo-Frontend.git"
call :ensure_repo "Configo-Web-Frontend" "https://github.com/Configo-ai/Configo-Web-Frontend.git"
call :ensure_repo "Configo-Developer-Frontend" "https://github.com/Configo-ai/Configo-Developer-Frontend.git"
call :ensure_repo "Configo-Deployment" "https://github.com/Configo-ai/Configo-Deployment.git"

echo.
where opencode >nul 2>nul
if errorlevel 1 (
    echo   Installing OpenCode...
    call npm install -g opencode-ai
)
echo   [OK] OpenCode ready

echo.
where auggie >nul 2>nul
if errorlevel 1 (
    echo   Installing Auggie CLI...
    call npm install -g @augmentcode/auggie@latest
)
echo   [OK] Auggie ready

echo.
if not exist "%USERPROFILE%\.config\opencode" mkdir "%USERPROFILE%\.config\opencode"
echo   Installing Superpowers for OpenCode...
call npm install "superpowers@git+https://github.com/obra/superpowers.git" --prefix "%USERPROFILE%\.config\opencode"
echo   [OK] Superpowers ready

echo.
echo   Configuring Context7 for OpenCode...
call npx -y ctx7 setup --opencode --yes
if errorlevel 1 (
    echo   [WARN] Context7 setup needs manual completion
) else (
    echo   [OK] Context7 configured
)

echo.
echo   Configuring OpenCode...
python "%ROOT%\tools\setup_opencode.py" configure --root "%ROOT%"
if errorlevel 1 exit /b 1
echo   [OK] OpenCode configured

echo.
echo   Setup complete!
echo   ---------------------------------------------------------
echo   Next steps:
echo   1. Run "auggie login" if this machine is not already authenticated
echo   2. Install the Augment GitHub App and select the Configo repos for remote indexing
echo   3. Open OpenCode and confirm both "augment-context-engine-local" and "augment-context-engine-remote" are enabled
echo   4. Copy Configo-Backend\.env.staging.example to Configo-Backend\.env.staging
echo   5. Fill in your staging credentials in Configo-Backend\.env.staging
echo   6. Run scripts\dev.bat to start all servers
echo   ---------------------------------------------------------
echo.
exit /b 0

:ensure_repo
if exist "%~1" (
    echo   [SKIP] %~1 already exists
) else (
    echo   Cloning %~1...
    git clone %~2
    if errorlevel 1 exit /b 1
    echo   [OK] %~1 cloned
)
exit /b 0
