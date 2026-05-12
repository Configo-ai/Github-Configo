# DRY Conventions

## Goal

Avoid duplicating logic across:
- components
- hooks
- API calls
- validation
- data transformations
- DTO shapes
- tenant-aware behavior

## Core Rule

If the same logic appears more than once, do not copy-paste it.

Instead:
- extract it to a shared hook
- move it to a utility
- centralize it in a service layer
- or move it to backend if it is business logic

## What Must Be Centralized

### API calls
All repeated API access should go through shared services or shared hooks.

### DTOs and types
Request and response shapes should be shared.
Do not redefine the same payload in multiple files.

### Validation
If validation is reused or affects correctness, it should be centralized in shared frontend validators or moved to backend.

### Transformations
Formatting and mapping logic used in multiple places should be extracted.

### View-state patterns
If multiple screens repeat the same loading, error, or submit flow, extract the pattern into a reusable hook or helper.

## What AI Should Check Before Coding

1. Does a similar component already exist?
2. Does a similar hook already exist?
3. Is there already a service or util for this?
4. Is the logic actually business logic that belongs in backend?
5. Can I extend an existing pattern instead of creating a parallel one?

## Anti-Patterns

Do not:
- duplicate fetch logic across pages
- duplicate DTO definitions
- duplicate field validation in multiple components
- reimplement pricing or rules in UI
- create nearly identical hooks for each page
- copy one component to make a second version with tiny differences
