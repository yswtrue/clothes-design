# BACKEND API AGENTS.MD

## OVERVIEW
Router layer for the FastAPI backend. Manages RESTful endpoints, request validation via Pydantic, and dependency injection for sessions and authentication.

## STRUCTURE
- `auth.py`: JWT generation, login, and registration flow.
- `materials.py`: CRUD for design materials and inventory.
- `roles.py`: RBAC management and permission assignments.
- `upload.py`: S3/Local file upload handling for design assets.
- `users.py`: User profile management and account settings.

## CONVENTIONS

### ROUTING
- Use `APIRouter` with consistent prefixing.
- Tag routers for clear OpenAPI documentation grouping.
- Keep route handlers thin; delegate complex logic to service or DB layers.

### DEPENDENCY INJECTION
- **Sessions**: Use `Depends(get_session)` for all database interactions.
- **Security**: Use `Depends(get_current_active_user)` to enforce authentication.
- **RBAC**: Use permission-specific dependencies to gate sensitive endpoints.

### VALIDATION & RESPONSES
- **Schemas**: Always use Pydantic models for request bodies and response serialization.
- **Status Codes**: Return appropriate HTTP status codes (201 for creation, 204 for deletion).
- **Exceptions**: Use `HTTPException` for predictable error responses to the client.

### ASYNC EXECUTION
- Define all path operations as `async def`.
- Use `await` for all database calls and I/O-bound operations.
- Avoid blocking calls within the request-response cycle.
