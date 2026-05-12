# Configo Knowledge

Central knowledge vault for alle Configo repos. Indeholder dokumentation, AI-konventioner, knowledge graph og hukommelse på tværs af sessioner, nu direkte i `Github-Configo`.

## Platform support

| Platform | Support |
|----------|---------|
| Linux | ✓ Fuldt understøttet |
| macOS | ✓ Fuldt understøttet (kræver [Homebrew](https://brew.sh)) |
| Windows (WSL) | ✓ Fuldt understøttet |
| Windows (native) | ✓ Understøttet via `scripts\\bootstrap.bat` |

> **Windows:** Brug `scripts\bootstrap.bat` til den native bootstrap. WSL er stadig fint, men ikke længere et krav.

## Opsætning på ny enhed

```bash
git clone https://github.com/Configo-ai/Github-Configo
cd Github-Configo
./scripts/setup.sh
./scripts/bootstrap.sh
```

Bootstrap installerer og konfigurerer automatisk:
- Claude Code
- GitHub CLI
- Obsidian
- Python, Graphify, MemPalace, Engram
- Alle Configo repos
- Git hooks, symlinks og MCP-server

## Hvad der synkroniseres via git

| Indhold | Placering |
|---------|-----------|
| Dokumentation | `backend/`, `frontend/`, osv. |
| Knowledge graph | `graphify/` |
| Graph cache | `graphify/cache/` |
| AI-hukommelse | `.mempalace/` |
| Skills & hooks | `.claude/` |

Nyere repo-retninger dokumenteres også her, herunder tværgående AI-arkitektur som `Configo-AI-Worker` og delte AI-kontrakter mellem frontends.

## Opdater knowledge graph manuelt

```bash
./scripts/update-graph.sh
```

Kører automatisk efter hvert commit via git hooks.
