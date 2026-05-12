# Web Frontend Repository

## Purpose

This repository contains the Configo web frontend.

It is responsible for:
- rendering pages and components
- handling user interaction
- managing local and route-level view state
- consuming backend APIs
- presenting tenant-aware branding and UX

## Non-Responsibilities

This repository does not own:
- pricing rules
- permission rules
- validation source of truth
- tenant security
- core business decisions

## Main Rule

If logic affects correctness, permissions, pricing, validation, or tenant isolation, it belongs in the backend.
