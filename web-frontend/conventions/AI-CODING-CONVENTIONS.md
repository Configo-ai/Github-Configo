# AI Coding Conventions

## Goal

Make changes that are:
- small
- reusable
- easy to reason about
- aligned with the migration toward backend-owned business logic

## Main Rules

- prefer existing hooks over new duplicated stateful code
- prefer existing components over copy-pasted UI
- prefer shared service or API layers over fetch calls inside components
- prefer shared types over redefining DTOs locally
- prefer backend contracts over frontend-only business rules

## Component Rules

Components should focus on:
- rendering
- composition
- UI event wiring
- lightweight presentation logic

Components should not become the home for:
- repeated fetch logic
- duplicated validation
- pricing calculations
- business rules
- tenant security logic

## Hook Rules

Use hooks for:
- reusable data fetching
- reusable view state
- shared UI workflows
- cross-component orchestration

Do not create multiple hooks with slightly different duplicated behavior when one shared hook can be extended safely.

## Service/API Rules

API calls should go through shared services or API helpers.
Do not scatter direct fetch or Supabase calls across components if the pattern is already centralized.

## Type Rules

Keep transport types shared.
Do not redefine the same request or response shape in multiple files.

## DRY Rule

Before writing new code, check:
1. does this logic already exist?
2. can I extend an existing hook, component, or util?
3. should this logic actually live in backend instead?
