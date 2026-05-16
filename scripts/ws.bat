@echo off
setlocal
set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..
python "%ROOT%\tools\setup_workspace.py" --root "%ROOT%" worktree %*
