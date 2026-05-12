# Error Format

Use one consistent error envelope across the API.

## Standard Shape

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

## Rules

- `code` should be stable and machine-friendly
- `message` should be human-readable
- `details` should be optional and structured
- do not return stack traces
- do not leak internal implementation details

## Common Codes

- `invalid_request`
- `unauthorized`
- `forbidden`
- `not_found`
- `conflict`
- `validation_failed`
- `internal_error`
