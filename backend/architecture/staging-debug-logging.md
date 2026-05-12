# Staging-Only Debug Logging

## Purpose

The backend should support detailed debug logging in staging without leaking that verbosity into production.

## Rules

1. normal application logging exists in all environments
2. detailed debug logging is staging-only
3. production must never emit debug logs
4. logging is controlled through environment variables
5. sensitive data must always be sanitized

## Recommended Environment Variables

```env
APP_ENV=local|staging|production
DEBUG=true|false
```

## Debug Enablement Rule

`Debug()` should only emit when:

```text
APP_ENV=staging and DEBUG=true
```

## Recommended Packages

- `internal/logger` for the wrapper
- `internal/transport/http/middleware` for request logging
- `internal/platform/config` for env loading

## Example Responsibilities

### `internal/logger`
- create structured logger
- expose `Info`, `Warn`, `Error`, `Debug`
- hold environment-aware debug gating

### request middleware
- generate or read request ID
- measure request duration
- log method, path, status, duration
- log sanitized metadata in staging only

### handlers and services
- use the wrapper instead of raw `slog` directly
- add contextual fields through helper methods
- log safe metadata, not secrets

## AI Rules

When adding logging:
- use the shared logger package
- do not create environment-specific logging rules in each handler
- keep debug gating centralized in the logger package
- prefer structured fields over string concatenation
