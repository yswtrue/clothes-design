# BACKEND TESTS KNOWLEDGE BASE

## OVERVIEW
Async-first test suite using `pytest` and `pytest-asyncio`. Focuses on isolated endpoint testing, database integrity, and asynchronous task verification.

## STRUCTURE
- `conftest.py`: Global fixtures (DB session, HTTPX client, auth helpers).
- `test_auth.py`: JWT, registration, and login flow validation.
- `test_rbac.py`: Permission and role-based access control checks.
- `test_storage.py`: S3/Local storage abstraction tests (Moto/Mock).
- `test_queue.py` / `test_worker.py`: Redis task production and consumption (Fakeredis).
- `test_materials.py` / `test_upload.py`: Domain-specific API tests.

## CONVENTIONS
- **Asyncio Mode**: Configured via `pytest_plugins = ("pytest_asyncio",)`. Use `async def test_*`.
- **Database**: `db_session` fixture uses an in-memory SQLite (`sqlite+aiosqlite`) engine.
- **API Testing**: Use the `client` (AsyncClient) fixture. It automatically handles dependency overrides for `get_session`.
- **Authentication**: 
  - Use `auth_headers` for requests requiring a logged-in user.
  - Use `test_user` to seed a standard user directly in the DB.
- **Isolation**: Each test involving `db_session` performs a cleanup (deleting Users) to ensure state independence.
- **Mocks**: 
  - Use `fakeredis` for Redis-related logic.
  - Use `moto[s3]` for storage testing to avoid real AWS calls.
- **Environment**: Use the `test_env` fixture to ensure stable JWT secrets and expiry during tests.

## FIXTURES SUMMARY
| Fixture | Type | Description |
| :--- | :--- | :--- |
| `db_session` | `AsyncSession` | Clean in-memory DB per test |
| `client` | `AsyncClient` | HTTPX client with DB overrides |
| `test_user` | `User` | Persisted user for testing |
| `auth_headers` | `dict` | Bearer token for authorized requests |
| `test_env` | `None` | Mocked JWT/Security settings |
