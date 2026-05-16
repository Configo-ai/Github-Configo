@echo off
setlocal EnableDelayedExpansion

set WIZARD_FLAGS=
for %%A in (%*) do (
    if "%%A"=="--yes" set WIZARD_FLAGS=--yes
    if "%%A"=="--non-interactive" set WIZARD_FLAGS=--yes
)

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
echo   Installing Python MCP SDK...
pip install --quiet mcp
if errorlevel 1 (
    echo   [WARN] pip install mcp failed - ws MCP server may not work
) else (
    echo   [OK] mcp installed
)

echo.
call :ensure_npm_global "opencode-ai@1.14.35" "opencode"
call :ensure_npm_global "@augmentcode/auggie@latest" "auggie"
call :ensure_npm_global "@tobilu/qmd" "qmd"
call :ensure_npm_global "@rynfar/meridian" "meridian" "--ignore-scripts"
call :ensure_npm_global "bun" "bun"

echo.
echo   Installing oh-my-openagent (ultrawork)...
call bunx oh-my-openagent install --no-tui --claude=yes --openai=no --gemini=no --copilot=no --skip-auth
if errorlevel 1 (
    echo   [WARN] oh-my-openagent install failed - run manually: bunx oh-my-openagent install
) else (
    echo   [OK] oh-my-openagent ready
)

echo.
echo   Setting Anthropic proxy environment variables...
setx ANTHROPIC_API_KEY "x" >nul
setx ANTHROPIC_BASE_URL "http://127.0.0.1:3456" >nul
echo   [OK] ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL set permanently

echo.
echo   Installing global wrappers...
for /f "tokens=*" %%i in ('npm prefix -g 2^>nul') do set NPM_BIN=%%i
if defined NPM_BIN (
    copy /Y "%SCRIPT_DIR%claude-opencode.bat" "%NPM_BIN%\claude-opencode.bat" >nul
    copy /Y "%SCRIPT_DIR%qmd.cmd" "%NPM_BIN%\qmd.cmd" >nul
    echo   [OK] claude-opencode + qmd wrapper installed to %NPM_BIN%
) else (
    echo   [WARN] Could not determine npm global bin directory
)

where claude >nul 2>nul
if errorlevel 1 (
    echo   [WARN] Claude Code CLI is not installed. Meridian still needs "claude login" later.
    goto :after_meridian_setup
)
echo.
echo   Running meridian setup (configures OpenCode plugin)...
call meridian setup
if errorlevel 1 (
    echo   [WARN] meridian setup failed - run manually after "claude login"
) else (
    echo   [OK] Meridian plugin configured for OpenCode
)
:after_meridian_setup

echo.
if not exist "%APPDATA%\opencode" mkdir "%APPDATA%\opencode"
echo   Installing Superpowers for OpenCode...
call npm install "superpowers@git+https://github.com/obra/superpowers.git" --prefix "%APPDATA%\opencode"
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
echo   Launching setup wizard...
python "%ROOT%\tools\setup_workspace.py" --root "%ROOT%" wizard %WIZARD_FLAGS%
if errorlevel 1 exit /b 1

echo.
echo   Setup complete!
echo   ---------------------------------------------------------
echo   Next steps:
echo   1. Run "claude login" if not already authenticated
echo   2. Launch OpenCode with "claude-opencode" (Meridian starts automatically)
echo   3. In OpenCode, run /init-deep to generate AGENTS.md files across all repos
echo   4. Use "scripts\ws.bat new <task> frontend backend" for cross-repo worktrees
echo   5. Copy Configo-Backend\.env.staging.example to Configo-Backend\.env.staging
echo   6. Fill in your staging credentials in Configo-Backend\.env.staging
echo   7. Run scripts\dev.bat to start all servers
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

:ensure_npm_global
where %~2 >nul 2>nul
if errorlevel 1 (
    echo   Installing %~2...
    call npm install -g %~1 %~3
) else (
    echo   [OK] %~2 ready
)
exit /b 0
