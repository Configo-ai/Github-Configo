@echo off
REM Configo Local Dev Launcher (Windows)
REM Starts: Backend (Go with staging Supabase) > All 3 Frontends (Vite)

setlocal EnableDelayedExpansion

echo.
echo   Configo Local Dev Launcher
echo   %time%
echo.

REM Paths
set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..
set BACKEND_DIR=%ROOT%\Configo-Backend
set MAIN_DIR=%ROOT%\Configo-Frontend
set WEB_DIR=%ROOT%\Configo-Web-Frontend
set DEVELOPER_DIR=%ROOT%\Configo-Developer-Frontend

REM Check if .env.staging exists
if not exist "%BACKEND_DIR%\.env.staging" (
    echo   ERROR: .env.staging not found in Configo-Backend
    echo   Copy .env.staging.example to .env.staging and fill in credentials
    exit /b 1
)

REM Start Go backend with staging env
echo Starting Go backend (staging Supabase)...
cd /d "%BACKEND_DIR%"
for /f "tokens=*" %%a in ('type .env.staging') do set %%a
start "Configo Backend" cmd /k "go run ./cmd/api/main.go"
echo   Backend started

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Start Configo-Frontend (main)
echo Starting Configo-Frontend on port 8080...
cd /d "%MAIN_DIR%"
start "Configo Main" cmd /k "npm run dev -- --host"
echo   Main started

REM Start Configo-Web-Frontend
echo Starting Configo-Web-Frontend on port 8081...
cd /d "%WEB_DIR%"
start "Configo Web" cmd /k "npm run dev -- --host"
echo   Web started

REM Start Configo-Developer-Frontend
echo Starting Configo-Developer-Frontend on port 8082...
cd /d "%DEVELOPER_DIR%"
start "Configo Developer" cmd /k "npm run dev -- --host"
echo   Developer started

echo.
echo   All servers started!
echo   ─────────────────────────────────────────────────────────
echo   Main Frontend:      http://localhost:8080
echo   Web Frontend:       http://localhost:8081
echo   Developer Frontend: http://localhost:8082
echo   Backend API:        http://localhost:9090 (or PORT from .env.staging)
echo   ─────────────────────────────────────────────────────────
echo.
