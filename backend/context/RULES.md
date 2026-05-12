# Backend Rules

## Core Rules

- backend is the source of truth
- keep handlers thin
- keep business logic in domain packages
- keep auth provider details isolated
- scope tenant data by `organization_id`
- use the shared logger package instead of ad hoc logging
- debug logging is staging-only
- document all HTTP endpoints in OpenAPI
- keep AI-facing API docs aligned with the OpenAPI contract
- enforce DRY across domain logic, repository code, DTOs, and error handling

## DO

- write small focused packages
- extract repeated logic
- wrap low-level errors with context
- test domain logic first
- log request IDs, status, and duration in middleware
- sanitize data before logging
- add Go doc comments to exported types and handlers
- include examples and validation rules in API docs
- reuse shared error helpers and DTOs

## DO NOT

- put business decisions in handlers
- call Supabase directly from handlers
- query DB directly from handlers
- duplicate pricing or validation rules across packages
- log passwords, tokens, cookies, auth headers, or raw personal data
- enable production debug logs
- rely on handler code as the only API documentation
- create parallel repository or service logic when an existing abstraction can be extended
