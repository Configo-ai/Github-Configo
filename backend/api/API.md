# API Documentation

## Purpose

This API is used to handle tenant-aware backend operations in Configo, such as organizations, users, quotes, pricing, and other domain workflows.

## Audience

This documentation is written for:
- developers
- integration partners
- AI agents that need to understand and use the API safely

## Source of Truth

- Machine-readable contract: `openapi/openapi.yaml` (OpenAPI 3.1.0)
- API conventions and standards: `docs/conventions/API-STANDARD.md`
- Human- and AI-friendly guide: this file
- Code-adjacent developer docs: Go doc comments in handlers, DTOs, and domain packages

## Base URL

Examples:
- `https://api.configo.ai`
- `https://api.promentum.com`

Tenant-aware frontend entrypoints may resolve to branded domains, but backend API domains should remain explicit and documented.

## Authentication

The API uses `Bearer` token in the `Authorization` header.

Example:

```http
Authorization: Bearer <token>
```

## Conventions

- requests and responses use `application/json`
- timestamps use ISO 8601 / RFC 3339
- IDs are strings with stable format
- amounts should use explicit documented units
- errors always use the shared error format
- tenant-aware operations must resolve organization scope before domain logic executes

## Error Format

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

## Common Status Codes

- `200 OK` – request succeeded
- `201 Created` – resource created
- `400 Bad Request` – invalid input
- `401 Unauthorized` – missing or invalid auth
- `403 Forbidden` – not allowed
- `404 Not Found` – resource does not exist
- `409 Conflict` – conflict with existing data
- `422 Unprocessable Entity` – semantically invalid input
- `500 Internal Server Error` – internal failure

---

# Endpoint Template

Use this format for each documented endpoint.

## POST /v1/users

Creates a new user.

### Description

Use this endpoint to create a user with email and name.

### Request Body

```json
{
  "email": "ada@example.com",
  "name": "Ada Lovelace"
}
```

### Validation Rules

- `email` must be a valid email
- `name` must be 1-100 characters

### Response: 201 Created

```json
{
  "id": "usr_123",
  "email": "ada@example.com",
  "name": "Ada Lovelace",
  "created_at": "2026-03-28T10:00:00Z"
}
```

### Possible Errors

- `400 invalid_request`
- `409 email_already_exists`

### Notes for AI Agents

- call this endpoint only once per intended new user creation
- if `409` is returned, do not blindly retry without checking whether the user already exists
- store the returned `id` for later calls

---

## GET /v1/users/{id}

Gets a user by ID.

### Path Parameters

- `id` – user ID

### Response: 200 OK

```json
{
  "id": "usr_123",
  "email": "ada@example.com",
  "name": "Ada Lovelace",
  "created_at": "2026-03-28T10:00:00Z"
}
```

### Possible Errors

- `404 user_not_found`

### Notes for AI Agents

- do not assume the user exists
- handle `404` explicitly

---

# Domain Models

## User

```json
{
  "id": "usr_123",
  "email": "ada@example.com",
  "name": "Ada Lovelace",
  "created_at": "2026-03-28T10:00:00Z"
}
```

### Fields

- `id`: stable unique ID
- `email`: unique email address
- `name`: display name
- `created_at`: creation timestamp in UTC

---

# Idempotency and Retries

- `GET` may be retried safely
- `POST` should only be retried with idempotency keys or safe deduplication
- `PATCH` should be retried carefully
- `DELETE` is logically idempotent, but clients should still handle `404`

# Pagination

If an endpoint returns lists, prefer this structure:

```json
{
  "items": [],
  "next_cursor": "abc123"
}
```

## Pagination Rules

- use `next_cursor` for the next page
- do not assume offset-based pagination
- stop when `next_cursor` is empty or missing

# Rate Limits

Document explicit rate limits when relevant.
When `429 Too Many Requests` is possible, document retry and backoff expectations.

# Security Notes

- never log bearer tokens
- mask personal data in logs
- do not return internal stack traces to clients

# AI Usage Notes

## Safe Behavior

- do not assume hidden fields or undocumented defaults
- use only documented endpoints
- handle errors explicitly
- do not guess enum values
- confirm destructive actions before execution

## Tooling Hints

- prefer JSON examples over prose
- use documented field names exactly
- treat response examples as contract guidance, not raw internal structs

# Changelog

## 2026-03-28

- first API documentation template version

## 2026-03-30

- added product API endpoints for CRUD, bulk import, tags, configurator mappings, and configurator sync

## GET /v1/products

Lists products for a specific organization.

Required query params:
- `org_id`
- optional `page_index`, `page_size`, `ids`, `skus`

Response shape:

```json
{
  "items": [],
  "total": 0
}
```

## GET /v1/products/{id}

Returns one product scoped by `org_id`.

## GET /v1/products/by-sku/{sku}

Returns one product scoped by `org_id`.

## POST /v1/products

Creates a product in the given `organization_id`.

## PATCH /v1/products/{id}

Applies a partial product patch. Explicit `null` values are preserved for nullable fields.

## DELETE /v1/products/{id}

Deletes a product.

## POST /v1/products/bulk-import

Imports only new SKUs for one organization and skips existing ones.

Response shape:

```json
{
  "items": []
}
```

## GET /v1/products/search

Searches products by SKU or name using `org_id`, `q`, and optional `limit`.

## GET /v1/products/tags

Returns distinct tags for an organization.

## PATCH /v1/products/tags

Applies the same tag array to multiple products.

## GET /v1/products/configurator-mappings

Returns backend-computed product-to-configurator mappings.

## POST /v1/products/{id}/sync-configurators

Triggers the existing configurator sync background flow for a product via backend.

## GET /v1/configurators

Lists configurators for an organization using `org_id`.

## POST /v1/configurators

Creates a configurator.

## GET /v1/configurators/active

Returns the reduced active configurator list used by selection UIs.

## PATCH /v1/configurators/order

Applies batch display-order updates.

## GET /v1/configurators/{id}

Returns a single configurator scoped by `org_id`.

## PATCH /v1/configurators/{id}

Applies a partial configurator patch.

## DELETE /v1/configurators/{id}

Soft-deletes a configurator.

## GET /v1/configurators/{id}/summary

Returns reduced configurator summary data for overview flows.

## GET /v1/configurators/{id}/config

Returns the minimal form-builder config payload.

## PUT /v1/configurators/{id}/config

Saves the form-builder config payload.

## GET /v1/configurators/{id}/configuration-data

Returns only `configuration_data`.

## PATCH /v1/configurators/{id}/configuration-data

Updates only `configuration_data`.

<!-- Duplicate configurator entries removed — see above for canonical list -->
