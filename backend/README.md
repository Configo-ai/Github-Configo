# Configo Go Backend

AI-friendly backend starter structure for a modular monolith in Go.

## Goals

- backend owns business logic
- tenant-first routing
- shared database with `organization_id` isolation
- thin handlers
- clear separation between domain, data, and platform/database layers
- staging-only debug logging with safe, sanitized output
- OpenAPI-first API documentation with an AI-friendly `API.md`
- strong DRY conventions across domain logic, DTOs, repositories, and error handling

## Read First

1. `SYSTEM.md`
2. `CLAUDE.md`
3. `docs/README.md`
4. `docs/conventions/DRY.md`

## AI Worker Boundary

Configo bruger en separat `Configo-AI-Worker` til AI-orchestration omkring configurators og assisted filling.

Backend forbliver stadig source of truth for:
- persisted configurator-data
- business rules
- validation rules
- permissions
- tenant isolation

AI workeren må gerne:
- oprette draft sessions
- hente relevant kontekst
- orkestrere chat og tool calls
- foreslå staged ændringer

AI workeren må ikke:
- erstatte backend-domænelogik
- eje persisted business state
- introducere en alternativ source of truth for regler og validering
