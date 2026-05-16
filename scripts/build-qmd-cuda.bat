@echo off
setlocal EnableDelayedExpansion

REM Build qmd's bundled node-llama-cpp against the locally installed CUDA toolkit.
REM
REM Why: qmd ships a prebuilt CUDA binary linked against CUDA 12 runtime. On
REM machines with only CUDA 13 installed, that binary crashes at first kernel
REM launch (ggml-cuda.cu:98). A local source-build links against your actual
REM CUDA install (13.x) so embeddings/rerank run on CUDA directly.
REM
REM Tradeoff vs the default Vulkan fallback: CUDA is ~3-5x faster than Vulkan
REM on a 3090 and uses VRAM more efficiently. Only worth running if you're
REM doing heavy semantic-search workloads.
REM
REM Prerequisites checked below: cl.exe (VS Build Tools), cmake, nvcc.

echo.
echo   qmd CUDA source-build
echo   ---------------------

set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..

echo.
echo   Checking prerequisites...

where cmake >nul 2>nul
if errorlevel 1 (
    echo   [FAIL] cmake not found on PATH.
    echo          Install: winget install Kitware.CMake
    exit /b 1
)
echo   [OK] cmake

where nvcc >nul 2>nul
if errorlevel 1 (
    echo   [FAIL] nvcc not found on PATH.
    echo          Install the CUDA Toolkit from https://developer.nvidia.com/cuda-downloads
    exit /b 1
)
echo   [OK] nvcc

where cl >nul 2>nul
if errorlevel 1 (
    echo   [FAIL] cl.exe ^(MSVC compiler^) not found on PATH.
    echo          Install Visual Studio Build Tools 2022 with the
    echo          "Desktop development with C++" workload, then re-run this
    echo          script from a "Developer Command Prompt for VS 2022".
    echo.
    echo          One-line install:
    echo            winget install Microsoft.VisualStudio.2022.BuildTools --override "--passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
    echo.
    echo          After install, open "x64 Native Tools Command Prompt for VS 2022"
    echo          and re-run this script.
    exit /b 1
)
echo   [OK] cl ^(MSVC^)

REM Resolve qmd's bundled node-llama-cpp location via npm prefix.
for /f "tokens=*" %%i in ('npm prefix -g 2^>nul') do set NPM_PREFIX=%%i
set NLC_DIR=%NPM_PREFIX%\node_modules\@tobilu\qmd\node_modules\node-llama-cpp

if not exist "%NLC_DIR%\package.json" (
    echo   [FAIL] Could not locate node-llama-cpp under qmd. Expected:
    echo            %NLC_DIR%
    echo          Run "npm install -g @tobilu/qmd" first.
    exit /b 1
)
echo   [OK] node-llama-cpp located at %NLC_DIR%

echo.
echo   Downloading llama.cpp source (this may take a minute)...
pushd "%NLC_DIR%"
call npx --no node-llama-cpp source download
if errorlevel 1 (
    popd
    echo   [FAIL] source download failed.
    exit /b 1
)

echo.
echo   Building with --gpu cuda (this may take 5-15 minutes)...
call npx --no node-llama-cpp source build --gpu cuda
if errorlevel 1 (
    popd
    echo   [FAIL] CUDA build failed. See output above.
    echo          Common causes:
    echo          - cl.exe is on PATH but CUDA can't find compatible MSVC headers
    echo            ^(run from "x64 Native Tools Command Prompt for VS 2022"^)
    echo          - sm_86 compute capability mismatch ^(unlikely on 3090^)
    exit /b 1
)
popd

echo.
echo   [OK] CUDA build complete.
echo.
echo   Switching QMD_LLAMA_GPU from vulkan -^> cuda...
setx QMD_LLAMA_GPU cuda >nul
echo   [OK] QMD_LLAMA_GPU=cuda persisted (effective in new shells).
echo.
echo   To benchmark, run in a NEW shell:
echo     qmd embed -f
echo.
echo   Expected: ~3-5 seconds for the current corpus vs ~12 seconds on Vulkan.
exit /b 0
