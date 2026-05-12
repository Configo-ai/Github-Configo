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

where gh >nul 2>nul || (
  echo [WARN] GitHub CLI not found. Trying winget install...
  where winget >nul 2>nul && winget install --id GitHub.cli --silent --accept-package-agreements --accept-source-agreements
)

where gh >nul 2>nul || (
  echo [ERROR] GitHub CLI is required. Install gh and re-run bootstrap.
  exit /b 1
)

gh auth status >nul 2>nul || (
  echo [ERROR] GitHub CLI is not authenticated. Run gh auth login and re-run bootstrap.
  exit /b 1
)

where node >nul 2>nul || (
  echo [WARN] Node.js not found. Trying winget install...
  where winget >nul 2>nul && winget install --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
)

where npm >nul 2>nul || (
  echo [ERROR] npm is required. Install Node.js and re-run bootstrap.
  exit /b 1
)

where claude >nul 2>nul || (
  echo Installing Claude Code...
  call npm install -g @anthropic-ai/claude-code
)

where jq >nul 2>nul || (
  echo [WARN] jq not found. Optional on Windows. Install manually if you need it.
)

where obsidian >nul 2>nul || (
  echo [WARN] Obsidian not found. Trying winget install...
  where winget >nul 2>nul && winget install --id Obsidian.Obsidian --silent --accept-package-agreements --accept-source-agreements
)

python -m pip --version >nul 2>nul || (
  echo [ERROR] pip is required. Install pip for Python and re-run bootstrap.
  exit /b 1
)

python -m pip show graphify >nul 2>nul || python -m pip install --user --quiet graphify
python -m pip show mempalace >nul 2>nul || python -m pip install --user --quiet mempalace

echo [WARN] Engram is not auto-installed on Windows by this script. Install manually if required.

python "%ROOT%\\tools\\bootstrap_workspace.py" configure-home --root "%ROOT%" --platform windows || exit /b 1
python "%ROOT%\\tools\\bootstrap_workspace.py" install-repo-support --root "%ROOT%" --platform windows || exit /b 1

if not exist "%ROOT%\\graphify\\GRAPH_REPORT.md" (
  call "%ROOT%\\scripts\\update-graph.bat" --silent
)

echo.
echo Bootstrap complete.
echo Next steps:
echo   1. Copy Configo-Backend\.env.staging.example to Configo-Backend\.env.staging
echo   2. Fill in staging credentials
echo   3. Run scripts\dev.bat
echo.
