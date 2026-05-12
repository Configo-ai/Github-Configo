@echo off
REM Configo Workspace Setup Script (Windows)
REM Clones all Configo repositories if they don't exist

setlocal EnableDelayedExpansion

echo.
echo   Configo Workspace Setup
echo   %time%
echo.

set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..

cd /d "%ROOT%"

REM Configo-Backend
if exist "Configo-Backend" (
    echo   [SKIP] Configo-Backend already exists
) else (
    echo   Cloning Configo-Backend...
    git clone https://github.com/Configo-ai/Configo-Backend.git
    echo   [OK] Configo-Backend cloned
)

REM Configo-AI-Worker
if exist "Configo-AI-Worker" (
    echo   [SKIP] Configo-AI-Worker already exists
) else (
    echo   Cloning Configo-AI-Worker...
    git clone https://github.com/Configo-ai/Configo-AI-Worker.git
    echo   [OK] Configo-AI-Worker cloned
)

REM Configo-Frontend
if exist "Configo-Frontend" (
    echo   [SKIP] Configo-Frontend already exists
) else (
    echo   Cloning Configo-Frontend...
    git clone https://github.com/Configo-ai/Configo-Frontend.git
    echo   [OK] Configo-Frontend cloned
)

REM Configo-Web-Frontend
if exist "Configo-Web-Frontend" (
    echo   [SKIP] Configo-Web-Frontend already exists
) else (
    echo   Cloning Configo-Web-Frontend...
    git clone https://github.com/Configo-ai/Configo-Web-Frontend.git
    echo   [OK] Configo-Web-Frontend cloned
)

REM Configo-Developer-Frontend
if exist "Configo-Developer-Frontend" (
    echo   [SKIP] Configo-Developer-Frontend already exists
) else (
    echo   Cloning Configo-Developer-Frontend...
    git clone https://github.com/Configo-ai/Configo-Developer-Frontend.git
    echo   [OK] Configo-Developer-Frontend cloned
)

REM Configo-Deployment
if exist "Configo-Deployment" (
    echo   [SKIP] Configo-Deployment already exists
) else (
    echo   Cloning Configo-Deployment...
    git clone https://github.com/Configo-ai/Configo-Deployment.git
    echo   [OK] Configo-Deployment cloned
)

echo.
echo   Setup complete!
echo   ─────────────────────────────────────────────────────────
echo   Next steps:
echo   1. Run scripts\bootstrap.bat to configure Claude, graphify and repo hooks
echo   2. Copy Configo-Backend\.env.staging.example to Configo-Backend\.env.staging
echo   3. Fill in your staging credentials in Configo-Backend\.env.staging
echo   4. Run scripts\dev.bat to start all servers
echo   ─────────────────────────────────────────────────────────
echo.
