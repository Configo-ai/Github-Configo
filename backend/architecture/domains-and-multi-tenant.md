# Domains and Multi-Tenant

## Domain Patterns

Examples:
- `alulock.configo.ai`
- `smart-group.promentum.com`

## Tenant Resolution

Recommended flow:

1. read `Host`
2. normalize host
3. look up exact hostname in `tenants`
4. resolve `organization_id`
5. load organization context
6. execute tenant-scoped domain logic

## Model

- `organizations` = business/data scope
- `tenants` = routing and hostname layer

This gives better overview and cleaner separation than forcing routing to live only on the organization record.
