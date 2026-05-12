# API Documentation Conventions

## Goal

Document the HTTP API in a way that works for:
- developers
- integration partners
- AI agents

## Recommended Source of Truth

Use three layers together:

1. **OpenAPI** in `openapi/openapi.yaml`
   - machine-readable HTTP contract
   - paths, parameters, auth, request/response schemas, examples

2. **Go doc comments**
   - package docs
   - exported handlers, DTOs, services, and interfaces
   - code-adjacent developer documentation

3. **AI-friendly markdown**
   - `docs/api/API.md`
   - explains flows, constraints, retry behavior, and safety notes

## Required API Documentation Fields

For every public endpoint, document:
- purpose
- auth requirements
- path/query/body parameters
- validation rules
- success responses
- error responses
- examples
- notes for AI agents when useful

## DTO Rule

Use explicit transport DTOs for documented request and response shapes.
Do not expose raw persistence structs as the public HTTP contract.

Recommended examples:
- `CreateUserRequestDTO`
- `UserResponseDTO`
- `ErrorEnvelopeDTO`

## Handler Comment Rule

Add doc comments to exported handlers and methods.

Example expectations:
- include the HTTP method and path
- describe the transport-level validation performed
- note which shared error envelope is returned
- explain any important safety constraints or idempotency notes

## Error Format Rule

API errors should follow one consistent envelope.

Example:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "email is required",
    "details": {
      "field": "email"
    }
  }
}
```

## Standard Error Helper Rule

Prefer shared helper functions for common HTTP error responses.

Examples:
- `WriteBadRequest`
- `WriteUnauthorized`
- `WriteForbidden`
- `WriteNotFound`
- `WriteConflict`
- `WriteValidationFailed`
- `WriteInternalError`

This keeps responses stable and reduces duplication across handlers.

## AI Documentation Rule

Add explicit sections such as:
- idempotency
- retry guidance
- destructive action warnings
- enum/value constraints
- pagination behavior
- rate limit behavior

AI systems should not be expected to infer these from Go code alone.
