# Configo Knowledge

Central knowledge vault for alle Configo repos. Indeholder dokumentation og AI-konventioner på tværs af sessioner, nu direkte i `Github-Configo`, mens kodekontekst hentes via Augment Context Engine MCP.

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

Setup installerer og konfigurerer automatisk:
- OpenCode
- Augment Context Engine MCP (`auggie`)
- Auggie CLI
- Superpowers plugin til OpenCode
- Context7 til OpenCode
- Alle Configo repos
- Workspace CLAUDE-filer og shared skills

Augment sættes op i en hybrid model:
- Lokal MCP til live workspace-ændringer og upush’et kode
- Remote MCP til GitHub-org og cross-repo kontekst via Augment GitHub App, men det tilføjes manuelt fra Augments MCP-konfigurationsside

## Hvad der synkroniseres via git

| Indhold | Placering |
|---------|-----------|
| Dokumentation | `backend/`, `frontend/`, osv. |
| Skills & hooks | `.claude/` |

Nyere repo-retninger dokumenteres også her, herunder tværgående AI-arkitektur som `Configo-AI-Worker` og delte AI-kontrakter mellem frontends.

## Augment MCP setup efter bootstrap

```bash
auggie login
```

Derefter:
- åbn `https://app.augmentcode.com/mcp/configuration` og vælg OpenCode remote MCP-konfigurationen
- installer Augment GitHub App på organisationen
- vælg Configo-repos i Augment til remote indeksering
- tilføj og autentificer remote MCP i OpenCode med Augments genererede config
- åbn OpenCode og bekræft at `augment-context-engine-local` står som enabled
