# BACKEND DB LAYER

**Generated:** 2026-04-05

## OVERVIEW
SQLAlchemy 2.0 async abstraction layer. Manages PostgreSQL connections via `asyncpg`, session lifecycle, and declarative schema models.

## STRUCTURE
- `base.py`: Async engine initialization and `get_session` dependency.
- `models.py`: Declarative mappings for users, designs, and materials.

## CONVENTIONS
- **Async Engine**: Configured with `pool_pre_ping=True` and `expire_on_commit=False`.
- **Database URL**: Auto-converts `postgresql://` to `postgresql+asyncpg://`.
- **Model Base**: All models inherit from `db.base.Base` (SQLAlchemy `DeclarativeBase`).
- **Timestamps**: Every table must have `created_at` with `server_default=func.now()`.
- **Versioning**: Designs use a child `DesignVersion` table for state tracking.
- **Foreign Keys**:
    - Use `ondelete="CASCADE"` for ownership relationships (e.g., User -> UserRole).
    - Use `ondelete="SET NULL"` for audit/preservation (e.g., User -> Design).
- **JSON Usage**: Use `JSON` column type for permissions and dynamic design metadata.
- **Relationships**: Always use `back_populates` and `cascade="all, delete-orphan"` for parent-to-child links.
- **Indexing**: Unique or high-cardinality columns (email, names) must be indexed.

## ANTI-PATTERNS
- **NO Explicit `session.commit()` in Models**: Models define structure, not transaction logic.
- **NO Plain `ForeignKey`**: Always specify `ondelete` behavior to prevent orphaned records.
- **NO Column Defaults in Python**: Prefer `server_default` to ensure consistency across clients.

## NOTES
- **Design Versioning**: `UniqueConstraint("design_id", "version")` enforces sequence integrity.
- **Audit Trail**: Root level rule "NO user deletion" is enforced by `ondelete="SET NULL"` on designs/materials.
