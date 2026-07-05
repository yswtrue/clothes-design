# BACKEND STORAGE LAYER

**Generated:** 2026-04-19
**Updated:** 2026-05-03

## OVERVIEW
Storage abstraction providing S3-compatible and local filesystem implementations. Factory pattern allows runtime selection via environment variables.

## STRUCTURE
- `storages.py`: Prefixed storage instances for different file types
- `base.py`: StorageService ABC defining upload/download/delete/list API
- `s3.py`: S3-compatible implementation (MinIO compatible)
- `local.py`: Local filesystem implementation
- `factory.py`: `get_storage_service()` factory function
- `thumbnail.py`: Thumbnail generation helper
- `exceptions.py`: Storage-specific exceptions

## AVAILABLE STORAGES
```python
from api.storage.storages import (
    prj_storage,              # PRJ template files
    preview_storage,          # PRJ preview images
    material_storage,         # Uploaded materials
    generated_image_storage,  # AI-generated images
    thumbnail_storage,        # Thumbnails
    upscaled_storage,         # Upscaled images
    output_tif_storage,       # Exported TIF files
)
```

## CONVENTIONS

### Database File Fields (IMPORTANT)
**Always use `FileType` from fastapi-storages for file-related database columns.**

```python
from fastapi_storages.integrations.sqlalchemy import FileType
from api.storage.storages import generated_image_storage

class MyModel(table=True):
    # CORRECT: Use FileType with appropriate storage
    image: Any = Field(
        default=None,
        sa_column=Column("image_path", FileType(storage=generated_image_storage), nullable=True)
    )
    
    # WRONG: Plain string field for file paths
    # image_path: Optional[str] = Field(default=None, max_length=500)
```

**Benefits of FileType:**
- Automatic URL generation via `model.image` (returns full URL)
- Consistent path handling across S3/local storage
- Integration with admin panel file uploads
- Type-safe file operations

### Storage Operations
- **Factory Pattern**: Use prefixed storage instances from `storages.py`
- **Environment Config**: 
  - `STORAGE_TYPE`: "s3" or "local" (default: "local")
  - S3 mode requires: `AWS_S3_BUCKET`, `AWS_S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
  - Local mode requires: `LOCAL_STORAGE_PATH` (default: "./uploads")
- **Path Conventions**: Use forward slashes for paths. Implementation handles OS-specific conversion.
- **Async Operations**: All storage operations are async. Use `await storage.upload()`, `await storage.download()`, etc.
- **Return Types**: 
  - `upload()` returns public URL (str)
  - `download()` returns bytes (handles both full URLs and filenames)
  - `list()` returns list of paths (List[str])

## ANTI-PATTERNS
- **NO Plain String Fields**: Never use `str` fields for file paths in models. Use `FileType`.
- **NO Direct Instantiation**: Never `S3Storage(...)` or `LocalStorage(...)`. Use prefixed storages.
- **NO Hardcoded Paths**: Never hardcode bucket names or storage roots. Use env vars.
- **NO Synchronous I/O**: All file operations must be async.

## USAGE EXAMPLE
```python
# In worker handler
from api.storage.storages import generated_image_storage, upscaled_storage

# Upload
url = await generated_image_storage.upload(image_bytes, "design_123.png")

# Download (handles both URLs and filenames)
content = await generated_image_storage.download(url)
content = await generated_image_storage.download("design_123.png")

# In model
record.image = "design_123.png"  # FileType handles URL generation
await session.commit()
print(record.image)  # Returns full URL like http://localhost:8000/api/files/generated/design_123.png
```

## NOTES
- **S3 Compatibility**: Tested with MinIO and AWS S3. Uses aioboto3 for async operations.
- **Local Storage**: Creates directory structure automatically.
- **Thumbnail**: `thumbnail.py` provides PIL-based thumbnail generation.
- **Used By**: API routes (upload, designs, templates), worker handlers (export, generate).
