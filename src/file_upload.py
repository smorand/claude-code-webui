"""File upload handling with validation and disk storage."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from tracing import trace_span

if TYPE_CHECKING:
    from collections.abc import Callable

    from config import Settings
    from database import Database

logger = logging.getLogger(__name__)


def create_file_upload_router(
    settings: Settings,
    db: Database,
    auth_dependency: Callable[..., Any] | None = None,
) -> APIRouter:
    """Create the file upload API router."""
    dependencies = [Depends(auth_dependency)] if auth_dependency else []
    router = APIRouter(prefix="/api/files", tags=["files"], dependencies=dependencies)

    def _validate_extension(filename: str) -> None:
        """Validate file extension against allowed list."""
        suffix = Path(filename).suffix.lower()
        if suffix not in settings.allowed_upload_extensions:
            raise HTTPException(
                status_code=422,
                detail=f"File type '{suffix}' is not allowed",
            )

    def _validate_size(size: int) -> None:
        """Validate file size against maximum."""
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        if size > max_bytes:
            raise HTTPException(
                status_code=422,
                detail=f"File size exceeds maximum of {settings.max_upload_size_mb} MB",
            )

    @router.post("/upload", status_code=201)
    async def upload_files(
        files: list[UploadFile],
    ) -> dict[str, list[dict[str, str | int]]]:
        """Upload one or more files to the configured upload directory."""
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        results: list[dict[str, str | int]] = []

        for upload in files:
            with trace_span("file.upload", attributes={"filename": upload.filename or "unknown"}):
                filename = upload.filename or "unnamed"

                _validate_extension(filename)

                file_path = upload_dir / filename
                if file_path.exists():
                    raise HTTPException(
                        status_code=409,
                        detail=f"File '{filename}' already exists in {settings.upload_dir}",
                    )

                content = await upload.read()
                size = len(content)

                if size == 0:
                    raise HTTPException(status_code=422, detail=f"File '{filename}' is empty")

                _validate_size(size)

                file_id = str(uuid.uuid4())
                file_path.write_bytes(content)

                content_type = upload.content_type or "application/octet-stream"

                await db.add_file(
                    file_id=file_id,
                    filename=filename,
                    size=size,
                    content_type=content_type,
                    storage_path=str(file_path),
                )

                results.append(
                    {
                        "file_id": file_id,
                        "filename": filename,
                        "size": size,
                        "content_type": content_type,
                        "path": str(file_path),
                    }
                )

                logger.info("File uploaded: %s (%d bytes) -> %s", filename, size, file_path)

        return {"files": results}

    return router
