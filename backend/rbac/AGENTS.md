# BACKEND RBAC LAYER

**Generated:** 2026-04-05

## OVERVIEW
JSONB-driven RBAC system implementing granular permission checks and role-to-user assignments. Default roles (admin, designer, viewer) are seeded on startup.

## STRUCTURE
- `permissions.py`: FastAPI dependency gates for route protection.
- `schemas.py`: Pydantic V2 models for role management and assignments.
- `service.py`: Core logic for permission evaluation and role CRUD.
- `seed.py`: Default role definitions and startup seeding logic.

## CONVENTIONS
- **Wildcard Permissions**: Use `*` for global access or `resource.*` for resource-wide access.
- **Dependency Injection**: Use `Depends(require_permission("perm.name"))` in API routers.
- **JSONB Schema**: Permissions stored as `dict[str, bool]` in the `Role` model.
- **Permission Resolution**: Evaluates all roles assigned to a user; any `True` grants access.
- **Async Logic**: All service methods and permission checks must be `async`.
- **Flush over Commit**: Service methods use `session.flush()` to allow caller-managed transactions.

## ANTI-PATTERNS
- **NO Sync Checks**: Never use synchronous database calls for permission validation.
- **NO Hardcoded Roles**: Check for permissions (e.g., `designs.create`), not role names.
- **NO Manual ID Assignment**: Use `service.assign_role_to_user` to manage associations.
- **NO Duplicate Seeds**: `seed_default_roles` checks for existence before creation.

## NOTES
- **Admin Role**: Grants `*` (total access) by default.
- **Designer Role**: Can create/update designs and manage materials.
- **Viewer Role**: Limited to `read` permissions for designs and materials.
- **Lifespan Integration**: `seed_default_roles` is invoked via `main.py:lifespan`.
