# Frontend Repository

## Purpose

This repository contains the Configo frontend.

It is responsible for:
- rendering UI
- handling user interaction
- managing local view state
- consuming backend APIs
- presenting tenant-aware branding and flows

## Non-Responsibilities

This repository does not own:
- pricing rules
- permission rules
- validation source of truth
- tenant security
- core business decisions

## Main Rule

If logic affects correctness, permissions, pricing, validation, or tenant isolation, it belongs in the backend.
