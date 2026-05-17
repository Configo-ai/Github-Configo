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
echo   Installing Python dependencies (mcp, textual)...
pip install --quiet mcp textual
if errorlevel 1 (
    echo   [WARN] pip install mcp/textual failed - ws MCP server or TUI may not work
) else (
    echo   [OK] mcp + textual installed
)

for /f "tokens=*" %%i in ('python -c "import json, pathlib; print(json.loads(pathlib.Path(r'tools/workspace_runtime.yaml').read_text())['opencode_version'])"') do set OPENCODE_VERSION=%%i
echo.
echo   Installing OpenCode %OPENCODE_VERSION%...
call npm install -g opencode-ai@%OPENCODE_VERSION%
if errorlevel 1 exit /b 1
echo   [OK] OpenCode pinned
call :ensure_npm_global "@augmentcode/auggie@latest" "auggie"
call :ensure_npm_global "@tobilu/qmd" "qmd"
call :ensure_npm_global "typescript-language-server" "typescript-language-server"

echo.
echo   Installing language servers for LSP-backed symbol queries...
where gopls >nul 2>nul
if errorlevel 1 (
    where go >nul 2>nul && (
        echo   Installing gopls (Go LSP)...
        call go install golang.org/x/tools/gopls@latest
        echo   [OK] gopls installed
    ) || (
        echo   [WARN] Go not on PATH; skipping gopls install
    )
) else (
    echo   [OK] gopls already on PATH
)
call :ensure_npm_global "pyright" "pyright-langserver"

echo.
echo   Installing mcp-language-server (Go binary, bridges any LSP to MCP)...
where mcp-language-server >nul 2>nul
if errorlevel 1 (
    where go >nul 2>nul && (
        call go install github.com/isaacphi/mcp-language-server@latest
        echo   [OK] mcp-language-server installed
    ) || (
        echo   [WARN] Go not on PATH; skipping mcp-language-server install
        echo          Install Go from https://go.dev/dl, then re-run setup.
    )
) else (
    echo   [OK] mcp-language-server already on PATH
)
echo.
echo   Note: rust-analyzer not auto-installed (no Rust repos detected).
echo         If you add Rust later: rustup component add rust-analyzer

echo.
echo   Installing Ollama + small local model (used by the MCP description compactor)...
where ollama >nul 2>nul
if errorlevel 1 (
    where winget >nul 2>nul && (
        call winget install --silent --accept-source-agreements --accept-package-agreements Ollama.Ollama
        echo   [OK] Ollama installed via winget
    ) || (
        echo   [WARN] winget not on PATH; install Ollama manually from https://ollama.com/download
    )
) else (
    echo   [OK] Ollama already on PATH
)
where ollama >nul 2>nul && (
    REM Pull the model used by tools/mcp_compactor.py. Idempotent — Ollama
    REM short-circuits when the manifest is already current.
    call ollama pull llama3.2:3b
    echo   [OK] llama3.2:3b ready
)

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
echo   Setting CLAUDE_CODE_SUBAGENT_MODEL=haiku (parallel Task-tool subagents default cheap)...
setx CLAUDE_CODE_SUBAGENT_MODEL haiku >nul
echo   [OK] CLAUDE_CODE_SUBAGENT_MODEL persisted

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
