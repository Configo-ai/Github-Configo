# Configo Workspace — Agent Instructions

## Architecture

Workspace repo orchestrating 6 sub-repos (gitignored, cloned by setup scripts). Sub-repos are **not** tracked in this repo.

```
Sub-repo                       Knowledge dir (in this repo)
Configo-Backend              →  backend/
Configo-AI-Worker            →  ai-worker/
Configo-Frontend             →  frontend/
Configo-Web-Frontend         →  web-frontend/
Configo-Developer-Frontend   →  developer-frontend/
Configo-Deployment           →  deployment/
```

- **Backend:** Go 1.22 modular monolith (`github.com/configo-ai/configo-backend`), Supabase DB, multi-tenant via `organization_id`
- **Frontends (×3):** React 18 + Vite + TypeScript + Tailwind CSS + shadcn/ui + Radix UI
- **Workspace config:** `Configo.code-workspace` (VS Code multi-root)
- All 3 frontends share the same Supabase instance — backend owns all migrations and edge functions

## Knowledge Dirs (read before editing)

Before making changes in a sub-repo, read from the matching knowledge dir in this repo. All paths below are **relative to the Github-Configo workspace root** — regardless of where the workspace is cloned on disk, the internal structure is always the same.

| Sub-repo | Knowledge dir | Key files |
|----------|---------------|-----------|
| Configo-Backend | `backend/` | `context/RULES.md`, `conventions/`, `architecture/`, `api/` |
| Configo-Frontend | `frontend/` | `context/RULES.md`, `conventions/` |
| Configo-Web-Frontend | `web-frontend/` | `context/RULES.md`, `conventions/` |
| Configo-Developer-Frontend | `developer-frontend/` | `context/RULES.md`, `conventions/` |
| Configo-AI-Worker | `ai-worker/` | `README.md` |
| Configo-Deployment | `deployment/` | `README.md` |

## Setup & Dev

```bash
scripts/setup.sh            # Clone repos, install tooling (Linux/macOS)
scripts/setup.bat           # Clone repos, install tooling (Windows)
scripts/dev.bat             # Start all 4 servers (backend + 3 frontends)
scripts/dev.sh              # Start all 4 servers (Linux/macOS)
```

Backend requires `Configo-Backend/.env.staging` (copy from `.env.staging.example`).

Server URLs:
- Main Frontend: `http://localhost:8080`
- Web Frontend: `http://localhost:8081`
- Developer Frontend: `http://localhost:8082`
- Backend API: `http://localhost:9090` (or `PORT` from `.env.staging`)

**Always run commands from the relevant sub-repo directory,** not the workspace root.

### Backend

```bash
go test ./...                                        # All tests
go test -run TestNewRouter ./internal/transport/http/  # Route conflict test
go run ./cmd/api/main.go                             # Start server
```

### Frontends (all three)

```bash
npm run dev              # Dev server (Vite)
npm run build            # Production build
npm run lint             # ESLint
npx vitest run           # Tests
```

Configo-Frontend may have different test setup — check its `package.json`.

## Backend Package Layout

```
cmd/api/                       # Entry point
internal/
  domain/                      # Business logic (tenants, organizations, pricing, quotes, authz)
  data/                        # Repositories and persistence behavior
  data/models/                 # Persistence models
  transport/http/              # HTTP handlers, middleware, router
  transport/http/response/     # Shared error/response helpers
  auth/supabase/               # Auth provider
  integrations/                # Third-party API clients
  logger/                      # Shared structured logging
  platform/config/             # Env config loading
  platform/database/           # Low-level DB plumbing, transaction helpers
```

## Critical Rules

### Backend is source of truth

Business logic, pricing, validation, permissions, tenant security live in backend only. Frontends do rendering, composition, UI state. If logic affects correctness, it belongs in backend.

### Thin handlers

Handlers parse requests, call domain services, write responses. No domain logic or direct DB access in handlers. Business logic lives in `internal/domain/`.

### Tenant scoping

Every DB query touching tenant data **MUST** filter by `organization_id`. Tenant resolved from JWT — never from headers or query params. `organization_id` = data scope. `tenant` = routing context (hostname). `organization` = business/data ownership.

### API conventions

- `/v1/` prefix, JSON only, `snake_case` field names, plural resource nouns
- Error envelope: `{ "error": { "code", "message", "details" } }`
- Use shared `internal/transport/http/response` helpers for all errors
- Cursor-based pagination (`next_cursor`), never offset-based
- OpenAPI contract in `openapi/openapi.yaml` — must be updated for every new endpoint
- Use explicit transport DTOs, never expose raw persistence structs as HTTP contract

### Logging

Use shared `internal/logger` wrapper. `Debug()` only when `APP_ENV=staging` AND `DEBUG=true`. Never log tokens, passwords, cookies, auth headers, or raw personal data.

### DRY mandate

Before writing new code, check if existing hooks, components, services, DTOs, or helpers already cover the need. Extend rather than duplicate.

## Feature Flags (All Frontends)

Every new feature (pages, routes, major UI) **MUST** be wrapped in `<FeatureFlag>` before merging to staging. Bug fixes and refactors skip flags.

```tsx
<FeatureFlag flag="dev-my-feature" fallback={<Old />}>
  <New />
</FeatureFlag>
```

Flag naming: kebab-case with `dev-` prefix. Requires a backend migration to insert the flag (disabled by default).

## Testing Priority (Backend)

Test in this order (highest blast radius first):
1. Tenant resolution (wrong org = data leak)
2. Authorization checks
3. Pricing and validation
4. Repository tenant scoping

Route conflict test (`TestNewRouter_NoRouteConflicts`) catches Go 1.22+ ServeMux pattern ambiguity — must pass before deploy.

## Commit Conventions

Format: `type: description` (types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`)

Small commits, clear intent. No vague messages.

## File Ownership

- This repo owns: `scripts/`, `tools/`, `hooks/`, `patches/`, `.claude/`, `.vscode/`, knowledge dirs, `index.md`, `README.md`
- Sub-repos own: their own code, config, CI, Dockerfiles
- Sub-repos are gitignored — never edit `.gitignore` to un-ignore them

## Augment Context Engine

`auggie` CLI is the primary code-context lookup tool — prefer over grep. Configure in `opencode.json` with `--add-workspace` for each sub-repo. Remote Augment MCP must be added manually from Augment's configuration page.