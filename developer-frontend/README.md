# Configo Developer Frontend

## Overview

This repository contains the internal developer/admin frontend for Configo.

It is used for:
- internal tools
- admin workflows
- configuration
- developer-facing UI

The frontend is responsible for:
- UI rendering
- user interaction
- developer workflows
- API consumption

It is not responsible for:
- business logic
- pricing rules
- validation source of truth
- permissions enforcement
- tenant security

These belong in the backend.

## Principles

### Frontend is a client
- call APIs
- render data
- handle interaction

### DRY
Avoid duplication across:
- hooks
- components
- API calls
- DTOs

### Backend owns logic
Move anything critical to backend.

## Docs

See `/docs`

## AI Worker Relation

`Configo-Developer-Frontend` må gerne bruge de samme AI-tools og AI-flows som `Configo-Frontend`, men den skal ikke eje implementeringen af agent-runtime.

Retningen er:
- fælles AI worker som separat service
- fælles HTTP-kontrakter for draft/chat/preview/product context
- intern tool-runtime i worker-repoet

Det betyder:
- developer-frontend må gerne bygge sin egen UI ovenpå de samme worker-endpoints
- developer-frontend skal ikke være source of truth for AI-orchestration
- AI-logik skal ikke kopieres ind i denne repo
