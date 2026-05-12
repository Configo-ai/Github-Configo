# Backend Repository

## Purpose

This repository contains the Configo Go backend.

It owns:
- business logic
- tenant resolution
- authorization
- persistence
- integrations
- API contracts
- all database migrations (`supabase/migrations/`)
- all edge functions (`supabase/functions/`)

## Main Rule

If logic affects correctness, pricing, validation, permissions, or tenant isolation, it belongs in the backend.

## Supabase Ownership

Backend is the single source of truth for all DB schema and edge functions.

All three frontend repos (Configo-Frontend, Configo-Developer-Frontend, Configo-Web-Frontend) share the same Supabase instance — they do not have their own migrations or edge functions. In local dev, `supabase start` runs once from this repo and all frontends connect to `localhost:54321`.

## Schema Layout

Domain schemas are organized in bounded contexts. Public tables are read-only (enforced by RLS blocking policies). New tables and migrations go in the appropriate domain schema, not in public.
