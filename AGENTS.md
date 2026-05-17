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
  - **Prefer `lex` first.** Try `searches: [{type: "lex", query: "..."}]` before
    `vec` or `hyde`. Lex is BM25 keyword search — instant, free, no LLM reranker.
    Only escalate to `vec`/`hyde` if lex returns nothing useful.
- For **symbol-level questions** ("where is X defined", "what calls Y", "find
  all references to Z", "rename W everywhere"), prefer the `lang-*` MCP servers
  (mcp-language-server bridges to gopls / typescript-language-server / pyright).
  Semantically-correct (type-aware) and ms-fast vs. seconds of grep approximation.
- For **graph / structural / similarity questions** ("what's the dependency
  graph of this package", "find duplicate logic", "blast radius if I change
  X"), call the `code-graph` MCP server. Pass `repo: "<alias>"` (e.g.
  `repo: "backend"`, `repo: "frontend"`) to scope results to one sub-repo.
  Omit `repo` to query across the whole workspace.
- Use `auggie` first for **conceptual** code lookups ("how does the auth flow
  work", "show me the rate-limiter implementation").
- Use `context7` for external framework and library docs.

Tool routing summary for code questions:

| Question shape | Tool to try first |
|---|---|
| "What calls / references X" | `lang-*` (LSP MCP) |
| "Rename X everywhere" | `lang-*` (LSP MCP) |
| "Compiler / type errors in this file" | `lang-*` (LSP MCP) |
| "Find duplicate / similar code" | `code-graph` (pass `repo:` to scope) |
| "Dependency / import graph" | `code-graph` (pass `repo:` to scope) |
| "How does feature Y work" | `auggie` |
| "Architecture / conventions" | `qmd-knowledge` |
| "Library API for npm package Z" | `context7` |

Do not mix workspace docs into code retrieval unless explicitly needed.

## Session History

Sessions are stored under `sessions/` **locally only** (gitignored). The
`workspace_conversation_id` correlation between Claude Code and OpenCode still
works for `/cross-resume`, but session bodies are not committed and not
searchable via qmd. Old sessions are auto-pruned after the retention period
configured in `tools/workspace_runtime.yaml` (`session_store.retention_days`).

## Shared Conversation Runtime

- All three clients (Claude Code, OpenCode, Kimi) get a workspace-owned
  `workspace_conversation_id` when launched via the workspace launcher.
- **Native-session resume**:
  - Claude Code: bidirectional. Stored Claude session id auto-resumes (`-r`).
  - OpenCode: bidirectional. Launcher back-fills the native session id by
    diffing `opencode session list --format json` before/after.
  - Kimi: one-way. We record Kimi's session id if you pass it explicitly
    (`-S <id>`), but upstream has no `session list --json` yet
    (MoonshotAI/kimi-cli#83), so the launcher falls back to `--continue` for
    "most recent in this cwd".
- `configo-helper` (PATH command) opens a TUI to pick a conversation + worktree
  and dispatch any of the three. `n` makes a new worktree, `F2` renames a
  conversation, `/` filters lists.
- `/cross-resume` inside Claude (or `scripts/cross-resume.*` from a shell)
  binds Claude or OpenCode to an existing workspace conversation.

## Worktrees

Cross-repo task workspaces live under `.worktrees/<task>/`. Prefer the TUI
(`configo-helper` → `n`); the underlying script is `scripts/ws.{bat,sh}`
(`new` / `status` / `open` / `remove`). When working inside `.worktrees/...`,
keep changes scoped there unless explicitly asked otherwise.

## Critical Rules

- Backend is source of truth for business logic, pricing, validation, permissions, and tenant security
- Thin handlers only in backend
- Every tenant-scoped query must filter by `organization_id`
- Use shared loggers and never log secrets or raw personal data
- Extend existing abstractions instead of duplicating them

## Feature Flags

Every new feature in a frontend must be wrapped in `<FeatureFlag>` before merging to staging. Bug fixes and refactors skip flags.

## File Ownership

- This repo owns `scripts/`, `tools/`, `.claude/`, `.vscode/`, knowledge dirs, `index.md`, `README.md`.
- `sessions/` is local-only (gitignored). Workspace-conversation correlation
  survives across machines via the id, not the body.
- Sub-repos own their own code, config, CI, and Dockerfiles. They stay gitignored.
