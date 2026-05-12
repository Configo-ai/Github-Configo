# Go Coding Conventions

## Package Roles

- `internal/domain/` owns business logic
- `internal/data/` owns repositories and persistence-facing behavior
- `internal/platform/database/` owns low-level db plumbing
- `internal/platform/config/` owns environment config loading
- `internal/logger/` owns structured application logging
- `internal/transport/` owns HTTP
- `internal/auth/` owns auth abstractions
- `internal/integrations/` owns third-party API clients

## Naming

- use `organization_id` consistently for tenant scoping
- use `tenant` for routing context
- use `organization` for business/data ownership

## Handler Rule

Handlers may parse requests, call services, and write responses.
Handlers may not contain domain logic or direct DB access.

## Logging Rule

Code should log through the shared logger wrapper so logging behavior is consistent across the codebase.
Use:
- `Info()` for normal lifecycle events
- `Warn()` for recoverable concerns
- `Error()` for failures
- `Debug()` only for staging-only diagnostics

## Documentation Rule

Add Go doc comments to:
- exported packages
- exported types
- handler structs and methods when they expose HTTP behavior
- important domain services and interfaces

Use OpenAPI for HTTP contract documentation and `docs/api/API.md` for human- and AI-friendly usage guidance.

## DRY Rule

Before creating new packages or helpers:
- look for an existing shared abstraction
- extend existing error helpers, DTOs, repository helpers, and domain services where reasonable
- do not split identical business rules across multiple domain packages
