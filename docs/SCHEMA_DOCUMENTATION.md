# Clothes Design Platform - Database Schema

## Overview
Complete database schema for the Clothes Design platform with 7 core tables, implemented using SQLAlchemy 2.0 and Alembic migrations.

## Table Structure

### 1. Users
Stores user account information and authentication details.
- `id` (INTEGER, PRIMARY KEY)
- `email` (VARCHAR 255, UNIQUE, INDEXED) - Login identifier
- `password_hash` (VARCHAR 255) - Hashed password
- `created_at` (TIMESTAMP) - Account creation time
- `updated_at` (TIMESTAMP) - Last modification time

### 2. Roles
Defines permission roles for role-based access control.
- `id` (INTEGER, PRIMARY KEY)
- `name` (VARCHAR 50, UNIQUE, INDEXED) - Role name (e.g., "admin", "designer", "viewer")
- `permissions` (JSONB) - Array of permission strings (e.g., ["design:create", "design:delete"])
- `created_at` (TIMESTAMP)

### 3. User Roles
Junction table linking users to roles (many-to-many).
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FK → users.id, CASCADE, INDEXED)
- `role_id` (INTEGER, FK → roles.id, CASCADE, INDEXED)
- `created_at` (TIMESTAMP)
- **UNIQUE CONSTRAINT**: (user_id, role_id) - Prevents duplicate role assignments

### 4. Designs
Stores design projects created by users.
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FK → users.id, SET NULL, INDEXED) - Owner (nullable for audit)
- `name` (VARCHAR 255) - Design project name
- `status` (VARCHAR 50, DEFAULT 'draft') - Current status (draft, published, archived)
- `created_at` (TIMESTAMP) - Creation time
- `updated_at` (TIMESTAMP) - Last modification time

### 5. Design Versions
Stores version history for each design (immutable snapshots).
- `id` (INTEGER, PRIMARY KEY)
- `design_id` (INTEGER, FK → designs.id, CASCADE, INDEXED) - Parent design
- `version` (INTEGER) - Version number
- `data` (JSONB) - Complete design snapshot containing:
  - Canvas dimensions
  - Layer positions and transformations
  - Color palettes
  - Print area coordinates
  - Metadata (e.g., theme, tags)
- `created_at` (TIMESTAMP) - Snapshot creation time
- **UNIQUE CONSTRAINT**: (design_id, version) - One snapshot per version number

### 6. Materials
User's library of uploaded design materials (images, textures, patterns).
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FK → users.id, SET NULL, INDEXED) - Owner (nullable for audit)
- `file_path` (VARCHAR 500) - S3 or storage path
- `file_type` (VARCHAR 50) - MIME type or file extension (e.g., "png", "jpg", "svg")
- `meta` (JSONB) - File metadata:
  - Original dimensions
  - File size
  - Upload timestamp
  - Processing status
- `created_at` (TIMESTAMP)

### 7. Templates
Built-in and custom design templates for quick start.
- `id` (INTEGER, PRIMARY KEY)
- `name` (VARCHAR 255) - Template name
- `type` (VARCHAR 50) - Template category (e.g., "tshirt", "hoodie", "print_area")
- `file_path` (VARCHAR 500) - Template file location
- `is_builtin` (INTEGER, DEFAULT 0) - 1 for built-in templates, 0 for user-created
- `created_at` (TIMESTAMP)

## Relationships

```
users ──┬────→ user_roles ──→ roles
        ├────→ designs ──────→ design_versions
        └────→ materials
```

## Key Design Decisions

### Foreign Key Constraints
- **CASCADE**: UserRole, DesignVersion (automatic cleanup)
- **SET NULL**: Design/Material → User (preserve orphan records for audit)

### JSONB Fields
- Store flexible, schema-less data
- Allow querying complex nested structures
- Suitable for: permissions, design parameters, metadata

### Indexing Strategy
- Unique index on `users.email` - fast authentication lookups
- Foreign key indexes - efficient joins and relationship queries
- Composite unique constraints - prevent duplicates

### Scalability Considerations
- Design versions are immutable (append-only)
- Users can be orphaned but not deleted (audit trail)
- JSONB fields support large nested structures
- Ready for partitioning on design_id or user_id

## Usage Examples

### Get user's designs with latest version
```sql
SELECT d.id, d.name, dv.data 
FROM designs d
LEFT JOIN design_versions dv ON d.id = dv.design_id 
  AND dv.version = (SELECT MAX(version) FROM design_versions WHERE design_id = d.id)
WHERE d.user_id = 1;
```

### Get user's permissions
```sql
SELECT DISTINCT jsonb_array_elements(r.permissions)
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
WHERE u.id = 1;
```

### List user's materials
```sql
SELECT * FROM materials WHERE user_id = 1 ORDER BY created_at DESC;
```

## Migration Information

**Initial Migration**: `001_initial_schema.py`
- Creates all 7 tables with proper indexes and constraints
- Fully reversible with downgrade support

**Migration Commands**:
```bash
# Apply pending migrations
cd backend && uv run alembic upgrade head

# Check current migration status
uv run alembic current

# Create new migration
uv run alembic revision -m "description"

# Rollback to previous state
uv run alembic downgrade -1
```

## Environment Setup

```bash
# Set DATABASE_URL
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/clothes_design_dev

# Apply schema
cd backend && uv run alembic upgrade head

# Verify tables created
psql $DATABASE_URL -c "\dt"
```

## Next Steps

1. Run Alembic migrations to create tables
2. Integrate with FastAPI using SQLAlchemy async session
3. Add user authentication endpoints
4. Implement design CRUD operations
5. Add tests for ORM models
