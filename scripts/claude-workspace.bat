@echo off
setlocal
set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..
python "%ROOT%\tools\workspace_launcher.py" claude --root "%ROOT%" --cwd "%CD%" -- %*
