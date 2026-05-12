# Configo Workspace

Multi-repo workspace for Configo development with integrated docs, knowledge graph, Claude tooling and automatic setup/bootstrap scripts.

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

### 3. Run bootstrap
The bootstrap script configures global Claude tooling, MemPalace, graphify wiring, hooks and repo-level Claude settings.

**Linux/Mac:**
```bash
./scripts/bootstrap.sh
```

**Windows:**
```cmd
scripts\bootstrap.bat
```

### 4. Configure staging credentials
```bash
cp Configo-Backend/.env.staging.example Configo-Backend/.env.staging
# Edit Configo-Backend/.env.staging with your staging credentials
```

### 5. Start all dev servers
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
├── graphify/                  # Knowledge graph output and cache
├── hooks/                     # Shared git hooks
├── patches/                   # Shared patches
├── .claude/                   # Team Claude config and skills
├── .obsidian/                 # Shared Obsidian vault metadata
├── index.md                   # Knowledge index
├── docs/knowledge-vault.md    # Migrated vault overview
├── scripts/
│   ├── setup.sh              # Clone all repos (Linux/Mac)
│   ├── setup.bat             # Clone all repos (Windows)
│   ├── bootstrap.sh          # Bootstrap Claude + knowledge tooling (Linux/Mac)
│   ├── bootstrap.bat         # Bootstrap Claude + knowledge tooling (Windows)
│   ├── update-graph.sh       # Refresh graphify output (Linux/Mac)
│   ├── update-graph.bat      # Refresh graphify output (Windows)
│   ├── dev.sh                # Start all servers (Linux/Mac)
│   └── dev.bat               # Start all servers (Windows)
├── tools/
│   ├── bootstrap_workspace.py # Shared bootstrap helper
│   ├── context_watchdog.py    # Claude hook helper
│   ├── graph_rebuild.py       # Claude graph rebuild helper
│   └── statusline.py          # Cross-platform Claude statusline
├── .vscode/
│   └── tasks.json            # VS Code/Windsurf task configuration
└── Configo.code-workspace    # VS Code workspace file
```

## Knowledge & Docs

- Main index: [index.md](./index.md)
- Vault overview: [docs/knowledge-vault.md](./docs/knowledge-vault.md)
- Knowledge graph report: [graphify/GRAPH_REPORT.md](./graphify/GRAPH_REPORT.md)

## Notes

- Backend runs with staging Supabase credentials from `Configo-Backend/.env.staging`
- Frontends use their own `.env` files for Supabase configuration
- All servers run in background; press `Ctrl+C` in the dev script terminal to stop all
- `configo-knowledge` is no longer part of setup; the main repo is now the source of truth for docs and knowledge tooling
