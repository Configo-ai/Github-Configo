# Testing Guidance

## Priority Order

Test these areas first — they have the highest blast radius:

1. tenant resolution (wrong org = data leak)
2. authorization checks (missing auth = security hole)
3. pricing and validation (wrong price = revenue impact)
4. repository tenant scoping (missing org_id filter = cross-tenant access)

## Critical Rule

Every test touching tenant data must make the active `organization_id` explicit.

## Test Structure

Tests live in `_test.go` files alongside the code they test. Use the `_test` package suffix for handler tests to test from the outside.

### Handler Tests

Handler tests use mock services that implement the domain `Service` interface. When a service interface gains a new method, all mocks must be updated — the compiler enforces this.

```go
// Mock must implement the full interface
type mockProjectsService struct {
    listResult projects.ListResult
    listErr    error
    // ... all other fields
}
```

### Route Conflict Test

`internal/transport/http/router_test.go` contains `TestNewRouter_NoRouteConflicts` which catches Go 1.22+ ServeMux pattern ambiguity at CI time. This prevents deploying a server that panics on startup due to conflicting route patterns.

### Running Tests

```bash
go test ./...                          # all tests
go test ./internal/transport/http/...  # handler + router tests
go test -run TestNewRouter ./internal/transport/http/  # route conflicts only
```

## What NOT to Test

- Don't test Go standard library behavior
- Don't test third-party packages
- Don't write tests that only assert mock return values
