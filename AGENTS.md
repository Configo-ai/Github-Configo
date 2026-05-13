# Configo Workspace — Agent Instructions

## Architecture

Workspace repo orchestrating 6 sub-repos (gitignored, cloned by setup scripts). Sub-repos are **not** tracked in this repo.

```
Sub-repo                    Knowledge dir (in this repo)
Configo-Backend           → backend/
Configo-AI-Worker         → ai-worker/
Configo-Frontend          → frontend/
Configo-Web-Frontend      → web-frontend/
Configo-Developer-Frontend→ developer-frontend/
Configo-Deployment        → deployment/
```

- Backend: Go 1.22 modular monolith (`github.com/configo-ai/configo-backend`), shared Supabase DB, multi-tenant via `organization_id`
- All 3 frontends: React 18 + Vite + TypeScript + Tailwind CSS + shadcn/ui
- Workspace config: `Configo.code-workspace` (VS Code multi-root)
- Augment Context Engine (`auggie` CLI) is the primary code-context lookup tool — prefer over grep.
- Use the hybrid Augment setup: local MCP for live workspace edits and remote MCP for GitHub-org cross-repo context.

## Setup & Dev

```bash
scripts/setup.sh            # Clone repos, install OpenCode, configure skills/context (Linux/macOS)
scripts/setup.bat           # Clone all sub-repos (Windows)
scripts/dev.bat             # Start all 4 servers (backend + 3 frontends)
```

**Augment Context Engine (required for code search):**
```bash
npm install -g @augmentcode/auggie@latest   # Install CLI
auggie login                                 # Browser auth, once per machine
```
OpenCode config lives at `%USERPROFILE%\.config\opencode\opencode.json`:
```json
{
  "plugin": ["%USERPROFILE%/.config/opencode/node_modules/superpowers"],
  "mcp": {
    "augment-context-engine-local": {
      "type": "local",
      "command": [
        "auggie",
        "--mcp",
        "--mcp-auto-workspace",
        "-w",
        "C:/Users/Lauritz/Documents/GitHub/Github-Configo",
        "--add-workspace",
        "C:/Users/Lauritz/Documents/GitHub/Github-Configo/Configo-Backend",
        "--add-workspace",
        "C:/Users/Lauritz/Documents/GitHub/Github-Configo/Configo-AI-Worker"
      ],
      "enabled": true
    },
    "augment-context-engine-remote": {
      "type": "remote",
      "url": "https://api.augmentcode.com/mcp",
      "enabled": true
    }
  }
}
```

Remote Augment still requires:
- `auggie login`
- Augment GitHub App installed on the org
- Configo repos selected in Augment for remote indexing

OpenCode also auto-discovers:
- Superpowers via the installed plugin
- Context7 via `ctx7 setup --opencode`
- `impeccable` and `caveman*` skills copied from `~/.agents/skills` into `~/.config/opencode/skills`

Server URLs:
- Main Frontend: `http://localhost:8080`
- Web Frontend: `http://localhost:8081`
- Developer Frontend: `http://localhost:8082`
- Backend API: `http://localhost:9090` (or PORT from `Configo-Backend/.env.staging`)

Backend requires `Configo-Backend/.env.staging` (copy from `.env.staging.example`).

## Running Commands

Always run from the relevant sub-repo directory, not the workspace root.

**Backend:**
```bash
go test ./...                                                    # All tests
go test -run TestNewRouter ./internal/transport/http/            # Route conflict test
go run ./cmd/api/main.go                                         # Start server
```

**Frontends (all three):**
```bash
npm run dev              # Dev server
npm run build            # Production build
npm run lint             # ESLint
npx vitest run           # Tests (Configo-Frontend may differ — check its package.json)
```

## Critical Architecture Rules

**Backend is source of truth.** Business logic, pricing, validation, permissions, tenant security live in backend only. Frontends do rendering, composition, UI state.

**Thin handlers.** Handlers parse requests, call domain services, write responses. No domain logic or direct DB access in handlers. Business logic lives in `internal/domain/`.

**Tenant scoping.** Every DB query touching tenant data MUST filter by `organization_id`. Tenant resolved from JWT — never from headers or query params.

**API conventions:**
- `/v1/` prefix, JSON only, `snake_case` field names
- Error envelope: `{ "error": { "code", "message", "details" } }`
- OpenAPI contract in `openapi/openapi.yaml` — must be updated for every new endpoint
- Use shared `internal/transport/http/response` helpers for errors

**Logging:** Use shared logger wrapper. `Debug()` only in staging (`APP_ENV=staging` + `DEBUG=true`). Never log tokens, passwords, cookies, auth headers, or raw personal data.

**DRY mandate.** Before writing new code, check if existing hooks, components, services, DTOs, or helpers already cover the need. Extend rather than duplicate.

## Key Docs an Agent Must Read

Before making changes in a sub-repo:
1. `<sub-repo>/CLAUDE.md` — links to knowledge dirs
2. `<knowledge-dir>/context/RULES.md` — repo-specific rules
3. `<knowledge-dir>/conventions/` — coding conventions, testing, anti-patterns
4. `Configo-Backend/SYSTEM.md` — system architecture and tenant model
5. `Configo-Backend/docs/api/API.md` — API reference (OpenAPI-based)

## Feature Flags (All Frontends)

Every new feature (pages, routes, major UI) MUST be wrapped in `<FeatureFlag>` before merging to staging. Bug fixes and refactors skip flags. Flag naming: kebab-case with `dev-` prefix. Requires a backend migration to insert the flag (disabled by default).

```tsx
<FeatureFlag flag="dev-my-feature" fallback={<Old />}>
  <New />
</FeatureFlag>
```

## Commit Conventions

Format: `type: description`
Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
Keep commits small, intent clear. No vague messages.

## Testing Priority (Backend)

Test in this order (highest blast radius first):
1. Tenant resolution (wrong org = data leak)
2. Authorization checks
3. Pricing and validation
4. Repository tenant scoping

Route conflict test (`TestNewRouter_NoRouteConflicts`) catches Go 1.22+ ServeMux pattern ambiguity — must pass before deploy.

## File Ownership

- This repo owns: `scripts/`, `tools/`, `hooks/`, `patches/`, `.claude/`, `.vscode/`, knowledge dirs, `index.md`, `README.md`
- Sub-repos own: their own code, config, CI, Dockerfiles
- Sub-repos are gitignored — never edit `.gitignore` to un-ignore them
