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

where git >nul 2>nul || (echo   [ERROR] Git is required& exit /b 1)
where python >nul 2>nul || (echo   [ERROR] Python is required& exit /b 1)
where node >nul 2>nul || (echo   [ERROR] Node.js is required& exit /b 1)
where npm >nul 2>nul || (echo   [ERROR] npm is required& exit /b 1)

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

for /f "tokens=*" %%i in ('python -c "import json, pathlib; print(json.loads(pathlib.Path(r'tools/workspace_runtime.yaml').read_text())['opencode_version'])"') do set OPENCODE_VERSION=%%i
echo.
echo   Installing OpenCode %OPENCODE_VERSION%...
call npm install -g opencode-ai@%OPENCODE_VERSION%
if errorlevel 1 exit /b 1
echo   [OK] OpenCode pinned
call :ensure_npm_global "@augmentcode/auggie@latest" "auggie"
call :ensure_npm_global "@tobilu/qmd" "qmd"

echo.
where kimi >nul 2>nul
if errorlevel 1 (
    echo   Installing Kimi Code CLI via uv...
    where uv >nul 2>nul || (
        echo   Installing uv...
        pip install --quiet --user uv
    )
    call uv tool install --python 3.13 kimi-cli
    if errorlevel 1 (
        echo   [WARN] Kimi CLI install failed - run `uv tool install --python 3.13 kimi-cli` manually
    ) else (
        echo   [OK] kimi installed - run `kimi` then `/login` to authenticate
    )
) else (
    echo   [OK] kimi already installed
)

echo.
echo   Applying local qmd patches (qmd.cmd shim + QMD_LLAMA_GPU=vulkan support)...
python "%ROOT%\tools\patch_qmd.py"

echo.
echo   Setting QMD_LLAMA_GPU=vulkan (avoids CUDA 12/13 ABI mismatch in qmd's prebuilt binary)...
setx QMD_LLAMA_GPU vulkan >nul
echo   [OK] QMD_LLAMA_GPU persisted

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
echo   1. Run "claude login" if Claude is not authenticated yet
echo   2. Launch Claude with "scripts\claude-workspace.bat"
echo   3. Launch OpenCode with "scripts\opencode-workspace.bat"
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
    call npm install -g %~1
) else (
    echo   [OK] %~2 ready
)
exit /b 0
