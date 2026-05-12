# Configo Workspace

Multi-repo workspace for Configo development with automatic setup scripts.

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
- configo-knowledge

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
├── configo-knowledge/         # Documentation & knowledge base
├── scripts/
│   ├── setup.sh              # Clone all repos (Linux/Mac)
│   ├── setup.bat             # Clone all repos (Windows)
│   ├── dev.sh                # Start all servers (Linux/Mac)
│   └── dev.bat               # Start all servers (Windows)
├── .vscode/
│   └── tasks.json            # VS Code/Windsurf task configuration
└── Configo.code-workspace    # VS Code workspace file
```

## Notes

- Backend runs with staging Supabase credentials from `Configo-Backend/.env.staging`
- Frontends use their own `.env` files for Supabase configuration
- All servers run in background; press `Ctrl+C` in the dev script terminal to stop all
