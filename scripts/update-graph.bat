@echo off
setlocal EnableExtensions EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..
set GRAPHIFY_OUT=%ROOT%\graphify

where python >nul 2>nul || (
  echo [ERROR] Python is required to update the graph.
  exit /b 1
)

python -m pip show graphify >nul 2>nul || python -m pip install --user --quiet graphify

if not exist "%ROOT%\graphify" mkdir "%ROOT%\graphify"

graphify --update >nul 2>nul
python "%ROOT%\tools\bootstrap_workspace.py" install-repo-support --root "%ROOT%" --platform windows >nul 2>nul
python "%ROOT%\tools\bootstrap_workspace.py" write-claude-md --root "%ROOT%" >nul 2>nul

echo Knowledge graph updated.
