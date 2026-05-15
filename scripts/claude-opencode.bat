@echo off
setlocal

netstat -an 2>nul | find "3456" | find "LISTENING" >nul 2>nul
if errorlevel 1 (
    echo Starting Meridian...
    start /B meridian
    timeout /t 3 /nobreak >nul
)

set ANTHROPIC_API_KEY=x
set ANTHROPIC_BASE_URL=http://127.0.0.1:3456
opencode %*
