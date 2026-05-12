# Configo Web Frontend

## Overview

This repository contains the public-facing or web frontend for Configo.

The frontend is responsible for:
- UI rendering
- user interaction
- page and route composition
- view state
- consuming backend APIs

The frontend is not the source of truth for:
- pricing rules
- validation rules
- authorization rules
- tenant security
- core business decisions

These belong in the backend.

## Architecture Direction

The project is moving toward:
- a thinner frontend
- backend-owned business logic
- explicit API contracts
- shared types
- less duplication across pages, hooks, and services

## Key Principles

### Frontend is a client
The frontend should:
- call APIs
- render server-backed data
- handle user input
- manage local UI state

It should not:
- reimplement backend rules
- duplicate validation logic
- contain pricing logic
- infer permissions
- own tenant security

### DRY
Avoid duplicating:
- API calls
- DTOs
- validation
- transformations
- hooks
- components

If logic appears twice, extract or reuse it.

### Prefer reuse over creation
Before adding new code:
- check existing hooks
- check existing components
- check existing services
- check shared types

### Move business logic to backend
If logic affects:
- correctness
- pricing
- permissions
- tenant behavior

it belongs in backend.

## Project Structure

```text
src/
  components/
  hooks/
  pages/
  services/
  lib/
  types/
```

## Docs

See `/docs`:

- `context/` → what this repo is and the repo rules
- `conventions/` → AI coding and DRY rules
- `ai/` → how Ruflo should work with this repo
- `archive/` → old docs kept temporarily for reference

## AI Usage

When using Ruflo or other AI:
- do not start coding immediately
- inspect existing patterns first
- avoid duplication
- prefer extending existing logic
- move business logic to backend when possible
