# BACKEND STORAGE LAYER

**Generated:** 2026-04-19

## OVERVIEW
Storage abstraction providing S3-compatible and local filesystem implementations. Factory pattern allows runtime selection via environment variables.

## STRUCTURE
- `base.py`: StorageService ABC defining upload/download/delete/list API
- `s3.py`: S3-compatible implementation (MinIO compatible)
- `local.py`: Local filesystem implementation
- `factory.py`: `get_storage_service()` factory function
- `thumbnail.py`: Thumbnail generation helper
- `exceptions.py`: Storage-specific exceptions

## CONVENTIONS
- **Factory Pattern**: Always use `get_storage_service()` to obtain storage instance. Never instantiate S3Storage/LocalStorage directly.
- **Environment Config**: 
  - `STORAGE_TYPE`: "s3" or "local" (default: "local")
  - S3 mode requires: `AWS_S3_BUCKET`, `AWS_S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
  - Local mode requires: `LOCAL_STORAGE_PATH` (default: "./uploads")
- **Path Conventions**: Use forward slashes for paths (e.g., "designs/123/preview.jpg"). Implementation handles OS-specific conversion.
- **Async Operations**: All storage operations are async. Use `await storage.upload()`, `await storage.download()`, etc.
- **Return Types**: 
  - `upload()` returns public URL (str)
  - `download()` returns bytes
  - `list()` returns list of paths (List[str])
- **Error Handling**: Raise `StorageError` subclasses for failures. Caller wraps in `HTTPException`.

## ANTI-PATTERNS
- **NO Direct Instantiation**: Never `S3Storage(...)` or `LocalStorage(...)` in application code. Use factory.
- **NO Hardcoded Paths**: Never hardcode bucket names or storage roots. Use env vars.
- **NO Synchronous I/O**: All file operations must be async. Never use `open()` or sync boto3 clients.
- **NO Missing Error Handling**: Always catch and re-raise storage exceptions with context.

## USAGE EXAMPLE
```python
from api.storage.factory import get_storage_service

storage = get_storage_service()
url = await storage.upload(file_bytes, "designs/123/preview.jpg")
content = await storage.download("designs/123/preview.jpg")
await storage.delete("designs/123/preview.jpg")
paths = await storage.list("designs/123/")
```

## NOTES
- **S3 Compatibility**: Tested with MinIO and AWS S3. Uses aioboto3 for async operations.
- **Local Storage**: Creates directory structure automatically. Uses aiofiles for async file I/O.
- **Thumbnail**: `thumbnail.py` provides PIL-based thumbnail generation with configurable sizes.
- **Used By**: API routes (upload, designs, templates), worker handlers (export, mockup).
