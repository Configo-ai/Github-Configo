# Logging Conventions

## Goal

Use one shared structured logging pattern across the backend.

## Required Behavior

- `Info`, `Warn`, and `Error` work in all environments
- `Debug` only writes logs when:
  - `APP_ENV=staging`
  - `DEBUG=true`
- production must never emit debug logs
- logging behavior must be controlled by environment variables

## Package Layout

Recommended packages:

```text
internal/
  logger/
    logger.go
  transport/
    http/
      middleware/
        request_logging.go
  platform/
    config/
      config.go
```

## Safe Logging Rules

Never log:
- passwords
- tokens
- auth headers
- cookies
- refresh tokens
- full request bodies containing personal data
- raw secrets from environment variables

Prefer logging:
- request ID
- method
- path
- status code
- duration
- organization ID when useful
- tenant hostname when useful
- sanitized metadata such as email domain instead of full email

## Middleware Rules

HTTP request logging middleware should log:
- method
- path
- status code
- duration
- request ID if present or generated

In staging, middleware may also log sanitized metadata such as:
- query string
- content type
- user agent

Do not log raw authorization headers or cookies.

## Usage Pattern

Use the wrapper consistently:

```go
logger.Info("server started")
logger.Error("db failed", err)
logger.Debug("request payload", "field_count", 3)
```

## Future Extensions

Later you can add:
- log sinks
- tracing correlation
- external log shipping
- structured redaction helpers
- tenant-aware log fields
