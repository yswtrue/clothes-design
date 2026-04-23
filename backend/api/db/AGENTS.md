# BACKEND DB LAYER

**Generated:** 2026-04-05

## OVERVIEW
SQLAlchemy 2.0 async abstraction layer. Manages PostgreSQL connections via `asyncpg`, session lifecycle, and declarative schema models with integrated soft delete functionality and automatic filtering.

## STRUCTURE
- `base.py`: Async engine initialization, `get_session` dependency, `SoftDeleteMixin` base class, and automatic soft delete filtering.
- `models.py`: Declarative mappings for users, designs, and materials. All models inherit from `SoftDeleteMixin`.

## CONVENTIONS
- **Async Engine**: Configured with `pool_pre_ping=True` and `expire_on_commit=False`.
- **Database URL**: Auto-converts `postgresql://` to `postgresql+asyncpg://`.
- **Model Base**: All models inherit from `SoftDeleteMixin` (defined in `base.py`) which provides soft delete functionality.
- **Timestamps**: Every table must have `created_at` with `server_default=func.now()`.
- **Soft Delete**: 
    - All models automatically have `deleted_at` field (Optional[datetime], indexed).
    - Instance methods: `.is_deleted` (property), `.soft_delete()` (method to mark as deleted).
    - **AUTOMATIC FILTERING**: All queries automatically exclude soft-deleted records by default.
    - To include deleted records: use `.execution_options(include_deleted=True)` on your query.
    - Usage:
      ```python
      # Soft delete
      user.soft_delete()
      await session.commit()
      
      # Query - automatically excludes deleted (NO MANUAL FILTERING NEEDED)
      result = await session.execute(select(User))
      users = result.scalars().all()  # Only non-deleted users
      
      # Query including deleted
      result = await session.execute(
          select(User).execution_options(include_deleted=True)
      )
      all_users = result.scalars().all()  # Including deleted users
      ```
- **Versioning**: Designs use a child `DesignVersion` table for state tracking.
- **Foreign Keys**:
    - Use `ondelete="CASCADE"` for ownership relationships (e.g., User -> UserRole).
    - Use `ondelete="SET NULL"` for audit/preservation (e.g., User -> Design).
- **JSON Usage**: Use `JSON` column type for permissions and dynamic design metadata.
- **Relationships**: Always use `back_populates` and `cascade="all, delete-orphan"` for parent-to-child links.
- **Indexing**: Unique or high-cardinality columns (email, names) must be indexed. `deleted_at` is indexed for efficient filtering.

## ANTI-PATTERNS
- **NO Explicit `session.commit()` in Models**: Models define structure, not transaction logic.
- **NO Plain `ForeignKey`**: Always specify `ondelete` behavior to prevent orphaned records.
- **NO Column Defaults in Python**: Prefer `server_default` to ensure consistency across clients.
- **NO Hard Deletes**: Use `.soft_delete()` method instead of `session.delete(model)`.
- **NO Manual Soft Delete Filtering**: Automatic filtering is enabled globally. Do NOT add `.where(Model.deleted_at == None)` manually.

## NOTES
- **Design Versioning**: `UniqueConstraint("design_id", "version")` enforces sequence integrity.
- **Audit Trail**: Root level rule "NO user deletion" is enforced by `ondelete="SET NULL"` on designs/materials and soft delete functionality.
- **Automatic Filtering**: Implemented via SQLAlchemy event listener on `do_orm_execute`. Applies to all SELECT queries automatically.
