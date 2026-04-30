from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import get_settings

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{file_path:path}")
async def serve_file(file_path: str):
    settings = get_settings().storage

    if settings.storage_type != "local":
        raise HTTPException(status_code=404, detail="File serving only available for local storage")

    base_path = Path(settings.local_storage_path)
    full_path = base_path / file_path

    # Security: ensure path doesn't escape base directory
    try:
        full_path.resolve().relative_to(base_path.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    return FileResponse(full_path)
