# API Standard

This document defines the conventions all Configo API endpoints must follow.
The machine-readable contract lives in `openapi/openapi.yaml`.

## Versioning

All endpoints are prefixed with `/v1/`. When a breaking change is required, a new prefix
(`/v2/`) is introduced and both versions are maintained until clients migrate.
The version prefix is part of the path, not a header or query parameter.

## Authentication

All protected endpoints require a Supabase JWT passed as a Bearer token:

```
Authorization: Bearer <access_token>
```

Endpoints that are explicitly public (newsletter subscribe, contact form, health check)
have no authentication requirement and are marked `security: []` in the OpenAPI spec.

## Tenant Scope

Tenant context is resolved from the authenticated user's JWT. Handlers must not accept
an organization ID as a header or query param for scoping purposes — the backend resolves
the tenant before handing off to domain logic. All data queries must be scoped by
`organization_id`.

## Request and Response Format

- Content type is always `application/json` for both requests and responses.
- Field names use `snake_case` throughout.
- Resource names in paths use plural nouns (e.g. `/v1/organizations`, `/v1/contacts`).
- Request bodies must be valid JSON; malformed JSON returns `400 invalid_request`.

## Timestamps

All timestamp fields use RFC 3339 format in UTC:

```
"created_at": "2026-03-29T10:00:00Z"
```

Never return Unix epoch integers as timestamps.

## Error Envelope

Every error response uses this exact envelope shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "name is required",
    "details": {}
  }
}
```

- `code` — machine-readable snake_case identifier (never changes between releases)
- `message` — human-readable description (may change)
- `details` — optional object with field-level or contextual information

Handlers must use the shared `internal/transport/http/response` package helpers to
write errors. Never write raw error strings directly to the response writer.

## Standard Status Codes

| Code | Meaning |
|------|---------|
| 200  | Request succeeded |
| 201  | Resource created |
| 204  | Success with no body (e.g. logout, delete) |
| 400  | Malformed request or validation failure |
| 401  | Missing or invalid authentication token |
| 403  | Authenticated but not authorised for this operation |
| 404  | Resource not found |
| 409  | Conflict with existing resource state |
| 422  | Semantically invalid input that passed structural validation |
| 500  | Unexpected internal failure |

## Pagination

List endpoints that may return many items use cursor-based pagination:

```json
{
  "items": [],
  "next_cursor": "abc123"
}
```

- Clients pass `?cursor=<next_cursor>` on the next request.
- When `next_cursor` is absent or empty, there are no more pages.
- Offset-based pagination (`?page=`, `?offset=`) must not be used.
- Default page size is 20 unless documented otherwise.

## Filtering

Query parameters for filtering follow the pattern `?filter[field]=value`.
Sorting uses `?sort=field` (ascending) or `?sort=-field` (descending).
Only documented filters are supported; unknown parameters are silently ignored.

## Naming Conventions

- Path segments: lowercase, hyphen-separated nouns (e.g. `/slug-available`)
- Query parameters: `snake_case`
- JSON field names: `snake_case`
- Error codes: `snake_case` verbs or nouns (e.g. `already_subscribed`, `invalid_request`)
- Boolean fields: named with a clear polarity (`gdpr_consent`, `is_super_admin`)

## Idempotency

- `GET` requests are always safe and idempotent.
- `DELETE` is logically idempotent; a second call on a deleted resource returns `404` or `204`.
- `POST` is not idempotent by default. Callers should not retry without deduplication logic.
- `PATCH` should be used for partial updates.

## Security Rules

- Never log Bearer tokens, passwords, or personal data.
- Never return internal stack traces or database errors to clients.
- Always validate and sanitise all input at the transport boundary.
- File path inputs must be sanitised to prevent directory traversal.

## OpenAPI Contract

The machine-readable contract for all endpoints is maintained in:

```
openapi/openapi.yaml
```

Every new endpoint must be documented there before merging. The OpenAPI spec uses
version 3.1.0. The spec is the authoritative reference; this document provides
human context and rationale.
