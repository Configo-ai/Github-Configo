# Configo Workspace — Agent Instructions

## Architecture

Workspace repo orchestrating 6 sub-repos. Sub-repos are cloned by setup scripts and are not tracked in this repo.

```text
Sub-repo                       Knowledge dir (in this repo)
Configo-Backend              -> backend/
Configo-AI-Worker            -> ai-worker/
Configo-Frontend             -> frontend/
Configo-Web-Frontend         -> web-frontend/
Configo-Developer-Frontend   -> developer-frontend/
Configo-Deployment           -> deployment/
```

## Retrieval Rules

- Use `qmd-knowledge` for repo knowledge (conventions, architecture, process docs).
  Pass `collections: ["knowledge-*"]` to scope (or list specific ones like
  `["knowledge-backend", "knowledge-frontend"]`). Conversation history is **not**
  indexed by qmd anymore — see "Session History" below.
- Use `auggie` first for live code behavior in the cloned code repos
- Use `context7` for external framework and library docs

Do not mix workspace docs into code retrieval unless explicitly needed.

## Session History

Sessions are stored under `sessions/` **locally only** (gitignored). The
`workspace_conversation_id` correlation between Claude Code and OpenCode still
works for `/cross-resume`, but session bodies are not committed and not
searchable via qmd. Old sessions are auto-pruned after the retention period
configured in `tools/workspace_runtime.yaml` (`session_store.retention_days`).

## Shared Conversation Runtime

- Claude and OpenCode share a workspace-owned `workspace_conversation_id`
- Their native session IDs are stored as metadata under the same workspace conversation
- Shared conversation logs live in `sessions/` and are tracked in Git

## Setup & Launch

```bash
bash scripts/setup.sh
scripts/setup.bat
bash scripts/claude-workspace.sh
scripts/claude-workspace.bat
bash scripts/opencode-workspace.sh
scripts/opencode-workspace.bat
bash scripts/ws
scripts/ws.bat
bash scripts/cross-resume.sh
scripts/cross-resume.bat
/cross-resume
scripts/install-linux-launchers.sh
scripts/install-windows-launchers.ps1
```

## Worktrees

Cross-repo task workspaces live under `.worktrees/<task>/`.

Use:
- `scripts/ws new <task> <repo> [repo...]`
- `scripts/ws status <task>`
- `scripts/ws open <task>`
- `scripts/ws remove <task>`
- `scripts/cross-resume.*` to list and resume shared workspace conversations across Claude and OpenCode
- `/cross-resume` inside Claude to browse and activate a shared workspace conversation

If you are working inside `.worktrees/...`, keep changes scoped there unless explicitly asked otherwise.

## Critical Rules

- Backend is source of truth for business logic, pricing, validation, permissions, and tenant security
- Thin handlers only in backend
- Every tenant-scoped query must filter by `organization_id`
- Use shared loggers and never log secrets or raw personal data
- Extend existing abstractions instead of duplicating them

## Feature Flags

Every new feature in a frontend must be wrapped in `<FeatureFlag>` before merging to staging. Bug fixes and refactors skip flags.

## File Ownership

- This repo owns `scripts/`, `tools/`, `.claude/`, `.vscode/`, knowledge dirs, `sessions/`, `index.md`, and `README.md`
- Sub-repos own their own code, config, CI, and Dockerfiles
- Sub-repos stay gitignored in this workspace repo
