---
description: List and reuse shared workspace conversations
argument-hint: [workspace_conversation_id] [client]
disable-model-invocation: true
---

Help the user continue work through the shared workspace conversation runtime.

Rules:
- Use the `configo-ws` MCP tools for conversation discovery and activation.
- The source of truth is the shared workspace conversation store, not Claude-native session ids.
- Treat the first argument as an optional `workspace_conversation_id`.
- Treat the second argument as an optional preferred client (`claude` or `opencode`).
- Never invent a conversation id. Always get it from the tool output.

Workflow:

1. If no `workspace_conversation_id` was provided:
   - Call the workspace tool that lists conversations.
   - Show the available shared conversations with their ids and human-readable names.
   - Ask the user which shared conversation they want to continue.
   - Tell them they can also use:
     - `bash scripts/cross-resume.sh claude <workspace_conversation_id>`
     - `bash scripts/cross-resume.sh opencode <workspace_conversation_id>`
     - `scripts\cross-resume.bat claude <workspace_conversation_id>`
     - `scripts\cross-resume.bat opencode <workspace_conversation_id>`

2. If a `workspace_conversation_id` was provided:
   - Call the workspace tool that activates that conversation for the current workspace scope.
   - Confirm which shared conversation is now active.
   - If the second argument is `claude`, recommend the Claude launcher command only.
   - If the second argument is `opencode`, recommend the OpenCode launcher command only.
   - Otherwise show both launcher options.

3. Keep the response short, practical, and action-oriented.
