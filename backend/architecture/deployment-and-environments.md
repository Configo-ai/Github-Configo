# Deployment and Environments

## Environments

- staging
- production

## Staging Domains (Cloudflare + Nginx)

| Service | Domain | Container Port |
|---------|--------|---------------|
| Web | `staging.configo.ai` | 3002 |
| API | `staging-api.configo.ai` | 8080 |
| Konfigurator (Frontend) | `staging-konfigurator.configo.ai` | 3000 |
| Developer | `staging-developer.configo.ai` | 3001 |

DNS is managed via Cloudflare (Proxied, SSL mode: Full with Origin Certificate).
Nginx on the server reverse-proxies each domain to the correct container port.

## Production Domains

- `api.configo.ai`
- `api.promentum.com`
- `smart-group.promentum.com`

## CI/CD Pipeline

Push to `main` in any repo triggers the full deploy flow:

1. **Build** — GitHub Actions builds Docker image and pushes to Scaleway Container Registry (`rg.pl-waw.scw.cloud/configo-registry/`)
2. **Update** — `repository_dispatch` triggers `update-release.yml` in Configo-Deployment, which updates `staging.json` with the new image tag (uses GitHub App token to trigger deploy)
3. **Deploy** — `deploy.yml` SSH's into the server, refreshes registry login, updates `.env` with image refs, runs `docker compose pull && docker compose up -d`, and health-checks the API

### Key files

- `Configo-Deployment/staging.json` — current image tags per service
- `Configo-Deployment/docker-compose.staging.yml` — service definitions
- `Configo-Deployment/.github/workflows/update-release.yml` — receives dispatch, commits image tag
- `Configo-Deployment/.github/workflows/deploy.yml` — SSH deploy with health check
- `Configo-Deployment/.github/workflows/promote.yml` — promotes staging images to production

### Server setup

- Instance: Scaleway (Warsaw), Docker + Docker Compose
- Directory: `/root/configo-staging/` with `docker-compose.yml` and `.env` (Supabase credentials)
- Registry login stored in `/root/.docker/config.json` (refreshed on each deploy)
- Dedicated SSH deploy key (ed25519, no passphrase) for CI

### GitHub Secrets

| Secret | Scope | Purpose |
|--------|-------|---------|
| `SCW_REGISTRY`, `SCW_SECRET_KEY` | Organization | Scaleway Container Registry |
| `DEPLOY_APP_ID`, `DEPLOY_APP_PRIVATE_KEY` | Organization | GitHub App for cross-repo dispatch |
| `STAGING_SSH_HOST`, `STAGING_SSH_USER`, `STAGING_SSH_KEY` | Deployment repo (staging env) | SSH access to staging server |

## Environment Variables

Typical variables:

```env
APP_ENV=local|staging|production
DEBUG=true|false
PORT=8080
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
CORS_ALLOWED_ORIGINS=https://configo.ai,https://promentum.com
```

## Logging Behavior by Environment

### Local
- normal app logs enabled
- debug logging optional for local development if you choose to extend it later

### Staging
- normal app logs enabled
- debug logging enabled only when `APP_ENV=staging` and `DEBUG=true`

### Production
- normal app logs enabled
- debug logging disabled

## CORS

Allow only known frontend origins.
Do not use permissive wildcard CORS in production unless deliberate.

## Operational Logging Rule

Production must not emit debug logs.
Sensitive data must never be logged in any environment.
