# Configo Workspace

Multi-repo workspace for Configo development with shared Claude Code / OpenCode / Kimi CLI tooling, separate code/docs retrieval, tracked conversation logs, and cross-repo worktree helpers.

## Quick Start

### 1. Clone this workspace
```bash
git clone <workspace-url> Github-Configo
cd Github-Configo
```

### 2. Run setup
Linux/macOS:
```bash
bash scripts/setup.sh
```

Windows:
```cmd
scripts\setup.bat
```

Setup will:
- clone all Configo code repos
- install `opencode-ai` pinned by `tools/workspace_runtime.yaml`
- install `@augmentcode/auggie`
- install `@tobilu/qmd`
- install Superpowers for OpenCode
- configure Context7 for OpenCode
- generate shared Claude Code / OpenCode / Kimi runtime config from the workspace manifest
- initialize the local `sessions/` conversation store (gitignored)

### 3. Launch the clients
Claude:

Linux/macOS:
```bash
bash scripts/claude-workspace.sh
```

Windows:
```cmd
scripts\claude-workspace.bat
```

Claude slash command:
```text
/cross-resume
/cross-resume <workspace_conversation_id>
/cross-resume <workspace_conversation_id> claude
/cross-resume <workspace_conversation_id> opencode
```

OpenCode:

Linux/macOS:
```bash
bash scripts/opencode-workspace.sh
```

Windows:
```cmd
scripts\opencode-workspace.bat
```

Cross-client resume:

Linux/macOS:
```bash
bash scripts/cross-resume.sh
bash scripts/cross-resume.sh claude <workspace_conversation_id>
bash scripts/cross-resume.sh opencode <workspace_conversation_id>
```

Windows:
```cmd
scripts\cross-resume.bat
scripts\cross-resume.bat claude <workspace_conversation_id>
scripts\cross-resume.bat opencode <workspace_conversation_id>
```

App launchers:

Windows:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-windows-launchers.ps1
```

Linux:
```bash
bash scripts/install-linux-launchers.sh
```

### 4. Configure staging credentials
```bash
cp Configo-Backend/.env.staging.example Configo-Backend/.env.staging
```

### 5. Start all dev servers
Linux/macOS:
```bash
bash scripts/dev.sh
```

Windows:
```cmd
scripts\dev.bat
```

## Context Model

- `auggie` is for live code retrieval only
- `qmd-knowledge` indexes workspace docs only. Pass `collections: ["knowledge-*"]`
  (or specific names) to scope a search. Session history is **not** indexed.
- `context7` is for external framework and library docs

Session bodies are kept locally only (gitignored) — they're not searchable via
qmd anymore. Cross-client conversation correlation (`/cross-resume`) still works.

## Shared Conversation Runtime

Claude and OpenCode share a workspace-owned conversation layer instead of trying to share one native runtime session ID.

Each shared conversation gets:
- a `workspace_conversation_id`
- optional Claude native session ID
- optional OpenCode native session ID
- tracked Markdown log under `sessions/`

Conversation logs are stored locally (gitignored) — the workspace correlation layer above is what survives across machines, not the conversation bodies themselves.
Use `cross-resume` to list human-readable conversation names and bind Claude or OpenCode to the same shared workspace conversation.
Inside Claude, the workspace also exposes `/cross-resume` via [.claude/commands/cross-resume.md](C:/Users/Lauritz/Documents/GitHub/Github-Configo/.claude/commands/cross-resume.md).

## Worktrees

Use the worktree helper for cross-repo task workspaces:

Linux/macOS:
```bash
bash scripts/ws new feature-login frontend backend ai-worker
bash scripts/ws status feature-login
bash scripts/ws open feature-login
bash scripts/ws remove feature-login
```

Windows:
```cmd
scripts\ws.bat new feature-login frontend backend ai-worker
scripts\ws.bat status feature-login
scripts\ws.bat open feature-login
scripts\ws.bat remove feature-login
```

Task workspaces live under `.worktrees/<task>/`.

## Server URLs

- Main Frontend: `http://localhost:8080`
- Web Frontend: `http://localhost:8081`
- Developer Frontend: `http://localhost:8082`
- Backend API: `http://localhost:9090`

## Workspace Structure

```text
Github-Configo/
├── Configo-AI-Worker/
├── Configo-Backend/
├── Configo-Deployment/
├── Configo-Developer-Frontend/
├── Configo-Frontend/
├── Configo-Web-Frontend/
├── ai-worker/
├── backend/
├── deployment/
├── developer-frontend/
├── docs/
├── frontend/
├── sessions/
├── web-frontend/
├── .worktrees/
├── scripts/
├── tools/
│   ├── runtime_manifest.py
│   ├── session_runtime.py
│   ├── setup_agents.py
│   ├── setup_workspace.py
│   ├── workspace_launcher.py
│   └── workspace_runtime.yaml
├── README.md
└── AGENTS.md
```

## Notes

- setup does not write Anthropic proxy env vars into your shell or Windows profile
- `qmd` runs as one installation indexing only `knowledge-*` collections (sessions are local-only)
- `sessions/` is local-only (gitignored) and no longer indexed by qmd; auto-pruned after the retention period in `tools/workspace_runtime.yaml`
- `context7` remains the external docs channel
- desktop/app launchers can be installed with `scripts/install-windows-launchers.ps1` or `scripts/install-linux-launchers.sh`
- qmd defaults to Vulkan on Windows (CUDA 12/13 ABI mismatch in the prebuilt binary). For native CUDA, run `scripts\build-qmd-cuda.bat` after installing VS Build Tools — gives ~3-5x faster embedding/rerank vs Vulkan
- `configo-helper` is installed onto PATH by setup. With no args it opens the workspace TUI (Textual, three panes — conversations / worktrees / agent picker — dispatches Claude / OpenCode / Kimi with the right resume flag, prompts for stash/discard if sub-repos are dirty, `n` creates a new cross-repo worktree, auto-refreshes on `sessions/` and `.worktrees/` changes). Subcommands: `configo-helper status` (one-line workspace summary), `configo-helper doctor` (runs the workspace doctor). The shim bakes in `CONFIGO_REPO_ROOT` so it works from any directory.
- `scripts\ws-tui.bat` / `scripts/ws-tui.sh` are direct entry points to the TUI if you'd rather not rely on the PATH shim
- Setup installs **Ollama + Llama 3.2 3B** and wires a local-model description compactor (`tools/mcp_compactor.py`) in front of every MCP server. Verbose tool descriptions are rewritten to 1-2 sentences and cached on disk, cutting ~10-25K tokens off every turn's system prompt. Re-runs are a no-op once cached.
- `configo-helper profile <name>` filters the active MCP set to a task category. Profiles defined in `tools/workspace_runtime.yaml` (`refactor` / `debug` / `feature` / `docs` / `bare` / `all`). Useful for stretching subscription quotas before a heavy session — pick the smallest profile that covers your task, restore with `configo-helper profile all` when done.
