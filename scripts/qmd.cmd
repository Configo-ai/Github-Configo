@echo off
setlocal
for /f "tokens=*" %%i in ('npm prefix -g 2^>nul') do set NPM_PREFIX=%%i
node "%NPM_PREFIX%\node_modules\@tobilu\qmd\dist\index.js" %*
