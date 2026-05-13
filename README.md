# Configo Workspace

Multi-repo workspace for Configo development with integrated docs, Augment MCP context, OpenCode tooling and automatic setup scripts.

## Quick Start

### 1. Clone this workspace
```bash
git clone <workspace-url> Github-Configo
cd Github-Configo
```

### 2. Run setup script
**Linux/Mac:**
```bash
./scripts/setup.sh
```

**Windows:**
```cmd
scripts\setup.bat
```

This will clone all Configo repositories:
- Configo-Backend
- Configo-AI-Worker
- Configo-Frontend
- Configo-Web-Frontend
- Configo-Developer-Frontend
- Configo-Deployment

It will also:
- install OpenCode
- install Auggie CLI
- install Superpowers for OpenCode
- configure local Augment Context Engine with explicit sub-repo workspaces
- configure remote Augment Context Engine for GitHub-based cross-repo context
- run Context7 setup for OpenCode
- clean up legacy graphify/mempalace/engram state

### 3. Configure staging credentials
```bash
cp Configo-Backend/.env.staging.example Configo-Backend/.env.staging
# Edit Configo-Backend/.env.staging with your staging credentials
```

### 4. Start all dev servers
**Linux/Mac:**
```bash
./scripts/dev.sh
```

**Windows:**
```cmd
scripts\dev.bat
```

Or via VS Code/Windsurf:
- `Ctrl+Shift+P` → "Tasks: Run Task" → "Start Dev Servers (Staging)"

## Server URLs

- **Main Frontend:** http://localhost:8080
- **Web Frontend:** http://localhost:8081
- **Developer Frontend:** http://localhost:8082
- **Backend API:** http://localhost:9090 (or PORT from .env.staging)

## Workspace Structure

```
Github-Configo/
├── Configo-AI-Worker/        # AI worker and orchestration service
├── Configo-Backend/           # Go backend
├── Configo-Frontend/          # Main React frontend (port 8080)
├── Configo-Web-Frontend/      # Web frontend (port 8081)
├── Configo-Developer-Frontend/ # Developer frontend (port 8082)
├── Configo-Deployment/        # Deployment configs
├── ai-worker/                 # AI worker knowledge and docs
├── backend/                   # Backend docs, conventions, context
├── deployment/                # Deployment docs
├── developer-frontend/        # Developer frontend docs
├── frontend/                  # Frontend docs
├── web-frontend/              # Web frontend docs
├── hooks/                     # Shared git hooks
├── patches/                   # Shared patches
├── .claude/                   # Team Claude config and skills
├── .obsidian/                 # Shared Obsidian vault metadata
├── index.md                   # Knowledge index
├── docs/knowledge-vault.md    # Migrated vault overview
├── scripts/
│   ├── setup.sh              # Clone all repos (Linux/Mac)
│   ├── setup.bat             # Clone all repos (Windows)
│   ├── bootstrap.sh          # Legacy bootstrap helper (Linux/Mac)
│   ├── bootstrap.bat         # Legacy bootstrap helper (Windows)
│   ├── update-graph.sh       # Legacy helper kept only for migration messaging
│   ├── update-graph.bat      # Legacy helper kept only for migration messaging
│   ├── dev.sh                # Start all servers (Linux/Mac)
│   └── dev.bat               # Start all servers (Windows)
├── tools/
│   └── setup_opencode.py      # Shared OpenCode setup + cleanup helper
├── .vscode/
│   └── tasks.json            # VS Code/Windsurf task configuration
└── Configo.code-workspace    # VS Code workspace file
```

## OpenCode

- OpenCode is installed by `scripts/setup.sh` / `scripts/setup.bat`
- Augment Context Engine local MCP is configured as the primary multi-repo code context tool
- Augment Context Engine remote MCP is configured alongside it for GitHub-org cross-repo lookups
- Superpowers is installed as an OpenCode plugin
- Context7 is set up for library/docs lookups
- OpenCode discovers skills from `~/.agents/skills`, `.agents/skills/`, `~/.claude/skills`, and `.claude/skills`

## Notes

- You do not need to convert the nested Configo repos to git submodules for Augment to work
- The local Augment MCP uses `--add-workspace` for each cloned repo, so gitignored nested repos are still indexed as separate workspaces
- The remote Augment MCP requires the Augment GitHub App plus repo selection in Augment before cross-repo retrieval works
- Backend runs with staging Supabase credentials from `Configo-Backend/.env.staging`
- Frontends use their own `.env` files for Supabase configuration
- All servers run in background; press `Ctrl+C` in the dev script terminal to stop all
- `configo-knowledge` is no longer part of setup; the main repo is now the source of truth for docs and knowledge tooling
- Augment Context Engine MCP in OpenCode is now the preferred context layer instead of the old graphify/memory bootstrap flow
