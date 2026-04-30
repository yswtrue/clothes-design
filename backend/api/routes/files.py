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

    full_path = Path(file_path)

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    return FileResponse(full_path)
