# Frontend Rules

## Core Rules

- frontend is not the source of truth for business logic
- keep components focused on rendering and composition
- keep shared behavior centralized
- prefer backend contracts over frontend-only business rules
- avoid duplication across hooks, components, services, DTOs, and validation

## DO

- reuse existing hooks and services
- extract repeated view logic
- share DTOs and types
- move correctness-critical logic to backend
- keep API access patterns centralized

## DO NOT

- duplicate fetch or Supabase logic across components
- reimplement pricing in UI
- duplicate validation across forms without a shared helper
- infer tenant permissions from frontend state
- copy components to create near-identical versions
