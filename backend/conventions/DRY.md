# DRY Conventions

## Goal

Avoid duplication across:
- domain rules
- repository logic
- DTOs
- validation
- tenant resolution
- error envelopes
- logging patterns
- API documentation

## Core Rule

If a rule or pattern appears in more than one place, do not copy-paste it unless there is a clear and documented reason.

Prefer to:
- extract a shared domain helper
- reuse an existing repository abstraction
- reuse a shared DTO or mapper
- centralize a shared error helper
- centralize tenant resolution logic
- keep one OpenAPI contract instead of multiple drifting shapes

## What Must Be Shared

### 1. Domain rules
Pricing, validation, authorization, and workflow rules should have one backend source of truth.

### 2. Tenant resolution
Do not reimplement hostname parsing and organization resolution in multiple handlers or packages.

### 3. Repository patterns
Shared query filters, especially `organization_id` scoping, should be centralized when repeated.

### 4. DTOs and error envelopes
Do not redefine the same transport shapes in multiple places.

### 5. Logging
Use the shared logger wrapper and shared request middleware.

### 6. API contract
OpenAPI and API.md should describe one contract, not multiple inconsistent interpretations.

## What AI Should Check Before Coding

1. Does this domain rule already exist?
2. Is there already a repository or mapper for this entity?
3. Does an error helper already exist for this response?
4. Is there already a shared DTO or OpenAPI schema?
5. Can I extend an existing service instead of creating a second one?

## Anti-Patterns

Do not:
- duplicate validation in handlers and domain without reason
- duplicate tenant parsing in multiple packages
- duplicate repository code with only tiny differences
- duplicate API response shapes
- duplicate error response logic
- duplicate business logic from frontend into backend
