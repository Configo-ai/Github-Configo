@echo off
setlocal
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%..\tools\workspace_tui.py" --root "%SCRIPT_DIR%.." %*
