# Configo Frontend

## Overview

This repository contains the Configo frontend application.

The frontend is responsible for:
- UI rendering
- user interaction
- view state
- API consumption

The frontend is not the source of truth for:
- business logic
- pricing
- validation rules
- permissions
- tenant security

These belong in the backend.

## Architecture Direction

The project is moving toward:
- a thinner frontend
- backend-owned business logic
- explicit API contracts
- shared types
- less duplication

## Key Principles

### Frontend is a client
The frontend should:
- call APIs
- render data
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

## AI Assistant Direction

`Configo-Frontend` er første klient for den nye AI-assistent til configurator-workspace.

Retningen er:
- en feature-flagged `AI Assistant` tab
- chat til venstre og preview til højre
- draft-baserede ændringer med apply/discard
- preview click-to-target som kontekst for næste prompt
- produktkontekst via attach/search

Vigtig designregel:
- følg den eksisterende struktur i configurator-featuret
- følg eksisterende tab-, hook-, service- og preview-mønstre
- udvid den nuværende oplevelse fremfor at bygge en separat frontend-arkitektur

Frontend er stadig kun klient:
- den kalder worker/backend API'er
- den ejer ikke agent-logik
- den ejer ikke retrieval-logik
- den ejer ikke domænevalidering som source of truth
