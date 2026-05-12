# Backend Structure

## Recommended Structure

```text
cmd/
  api/

internal/
  transport/
    http/
      middleware/
  domain/
    tenants/
    organizations/
    pricing/
    quotes/
    authz/
  data/
    repositories/
    models/
  auth/
    supabase/
  integrations/
  logger/
  platform/
    config/
    database/
    logging/
```

## Layer Intent

### `domain`
Business logic and decisions.

### `data`
Repositories and business-facing persistence behavior.

### `platform/database`
Low-level DB setup, transaction helpers, migrations wiring, and query plumbing.

### `platform/config`
Environment loading and application config.

### `logger`
Reusable structured logging wrapper used by handlers, services, and middleware.

### `transport`
HTTP parsing and response writing.

### `auth/supabase`
Supabase-specific auth provider code.

### `integrations`
Third-party systems outside your core database.

### sibling AI worker
A separate AI worker may sit beside the backend for orchestration-heavy AI flows such as configurator assistance, retrieval, and guided filling.

That worker should:
- consume backend-owned APIs and persisted data
- operate on draft state and staged actions
- keep AI/runtime dependencies isolated from the core backend

That worker should not:
- become the source of truth for business rules
- bypass backend ownership of correctness-sensitive logic

## Boundary Rules

- handlers call domain services
- domain uses interfaces
- data and auth implement interfaces
- platform/database stays below data
- business logic does not live in transport or raw DB plumbing
- all app code should use the shared logger package rather than creating custom loggers ad hoc
- repeated repository or transport patterns should be extracted, not duplicated
- AI orchestration services may exist outside the backend, but correctness-sensitive decisions must still resolve through backend-owned rules and contracts
