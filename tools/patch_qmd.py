"""Idempotent post-install patcher for the global @tobilu/qmd npm package.

Run this after `npm install -g @tobilu/qmd`. It re-applies two local fixes
that npm wipes on every (re)install:

  1. Windows-only: rewrite the npm-generated `qmd.cmd` shim so it invokes
     `dist/cli/qmd.js` (the real CLI) instead of `dist/index.js` (the SDK
     library, which has no CLI handling and silently exits).

  2. Patch qmd's `dist/llm.js` so the `QMD_LLAMA_GPU` env var accepts
     "vulkan" / "metal" / "cuda" as explicit backend choices. Upstream
     only accepts "false" / "off" / "none" — anything else falls through
     to "auto", which picks CUDA on Windows and crashes on CUDA-13-only
     systems (qmd's prebuilt node-llama-cpp binary is built for CUDA 12).

Both patches are detect-then-apply; running this multiple times is a no-op.

Run via `python tools/patch_qmd.py` after qmd is installed.
"""
from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


# --- Discovering the qmd install ---------------------------------------------


def _npm_prefix() -> Path | None:
    cmd = ["npm.cmd", "prefix", "-g"] if platform.system() == "Windows" else ["npm", "prefix", "-g"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    path = result.stdout.strip()
    return Path(path) if path else None


# --- Patch 1: qmd.cmd shim (Windows only) -----------------------------------


_QMD_CMD_FIXED = (
    "@echo off\r\n"
    "setlocal\r\n"
    "for /f \"tokens=*\" %%i in ('npm prefix -g 2^>nul') do set NPM_PREFIX=%%i\r\n"
    "node \"%NPM_PREFIX%\\node_modules\\@tobilu\\qmd\\dist\\cli\\qmd.js\" %*\r\n"
)


def patch_qmd_cmd(npm_prefix: Path) -> str:
    shim = npm_prefix / "qmd.cmd"
    if not shim.exists():
        return f"skip: {shim} not found"
    current = shim.read_text(encoding="utf-8", errors="replace")
    if "dist\\cli\\qmd.js" in current:
        return "ok: qmd.cmd already patched"
    shim.write_text(_QMD_CMD_FIXED, encoding="utf-8")
    return "fixed: qmd.cmd rewritten to invoke dist/cli/qmd.js"


# --- Patch 2: dist/llm.js QMD_LLAMA_GPU accept-list -------------------------


_LLM_OLD = '''            // Allow override via QMD_LLAMA_GPU: "false" | "off" | "none" forces CPU
            const gpuOverride = (process.env.QMD_LLAMA_GPU ?? "").toLowerCase();
            const forceCpu = ["false", "off", "none", "disable", "disabled", "0"].includes(gpuOverride);
            const loadLlama = async (gpu) => await getLlama({
                build: "autoAttempt",
                logLevel: LlamaLogLevel.error,
                gpu,
            });
            let llama;
            if (forceCpu) {
                llama = await loadLlama(false);
            }
            else {
                try {
                    llama = await loadLlama("auto");
                }
                catch (err) {
                    // GPU backend (e.g. Vulkan on headless/driverless machines) can throw at init.
                    // Fall back to CPU so qmd still works.
                    process.stderr.write(`QMD Warning: GPU init failed (${err instanceof Error ? err.message : String(err)}), falling back to CPU.\\n`);
                    llama = await loadLlama(false);
                }
            }'''


_LLM_NEW = '''            // Allow override via QMD_LLAMA_GPU:
            //   "false"/"off"/"none"/"0" → CPU
            //   "vulkan"/"metal"/"cuda"  → force that backend
            //   (unset / anything else)   → "auto"
            const gpuOverride = (process.env.QMD_LLAMA_GPU ?? "").toLowerCase();
            const forceCpu = ["false", "off", "none", "disable", "disabled", "0"].includes(gpuOverride);
            const explicitGpu = ["vulkan", "metal", "cuda"].includes(gpuOverride) ? gpuOverride : null;
            const loadLlama = async (gpu) => await getLlama({
                build: "autoAttempt",
                logLevel: LlamaLogLevel.error,
                gpu,
            });
            let llama;
            if (forceCpu) {
                llama = await loadLlama(false);
            }
            else if (explicitGpu) {
                try {
                    llama = await loadLlama(explicitGpu);
                }
                catch (err) {
                    process.stderr.write(`QMD Warning: ${explicitGpu} init failed (${err instanceof Error ? err.message : String(err)}), falling back to CPU.\\n`);
                    llama = await loadLlama(false);
                }
            }
            else {
                try {
                    llama = await loadLlama("auto");
                }
                catch (err) {
                    // GPU backend (e.g. Vulkan on headless/driverless machines) can throw at init.
                    // Fall back to CPU so qmd still works.
                    process.stderr.write(`QMD Warning: GPU init failed (${err instanceof Error ? err.message : String(err)}), falling back to CPU.\\n`);
                    llama = await loadLlama(false);
                }
            }'''


def patch_llm_js(npm_prefix: Path) -> str:
    llm = npm_prefix / "node_modules" / "@tobilu" / "qmd" / "dist" / "llm.js"
    if not llm.exists():
        return f"skip: {llm} not found"
    content = llm.read_text(encoding="utf-8")
    if 'explicitGpu' in content:
        return "ok: llm.js already patched"
    if _LLM_OLD not in content:
        return "warn: llm.js shape changed — manual review needed (upstream qmd may have changed)"
    llm.write_text(content.replace(_LLM_OLD, _LLM_NEW), encoding="utf-8")
    return "fixed: llm.js patched to accept QMD_LLAMA_GPU=vulkan|metal|cuda"


# --- Entrypoint -------------------------------------------------------------


def main() -> int:
    prefix = _npm_prefix()
    if prefix is None:
        print("ERROR: could not resolve `npm prefix -g`", file=sys.stderr)
        return 1
    results = []
    if platform.system() == "Windows":
        results.append(patch_qmd_cmd(prefix))
    results.append(patch_llm_js(prefix))
    has_warning = False
    for line in results:
        ok = line.startswith(("ok:", "fixed:"))
        if not ok:
            has_warning = True
        prefix_char = "[OK]" if ok else "[!] "
        print(f"  {prefix_char} {line}")
    # Non-zero on warnings so the caller (setup.bat / setup.sh) can react.
    return 1 if has_warning else 0


if __name__ == "__main__":
    sys.exit(main())
