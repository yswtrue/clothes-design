"""Task queue data models."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskPayload(BaseModel):
    """Task submission payload."""

    task_type: str = Field(..., description="Task type (e.g., generate_pattern, upscale_image)")
    user_id: int = Field(..., description="User ID submitting the task")
    data: dict[str, Any] = Field(default_factory=dict, description="Task-specific parameters")


class TaskStatus(BaseModel):
    """Task status response."""

    task_id: str = Field(..., description="Unique task identifier (UUID)")
    task_type: str = Field(..., description="Task type")
    user_id: int = Field(..., description="User ID")
    status: Literal["pending", "processing", "completed", "failed"] = Field(
        ..., description="Current task status"
    )
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    data: dict[str, Any] = Field(default_factory=dict, description="Task-specific parameters")
    result: dict[str, Any] | None = Field(None, description="Task result data if completed")
    error: str | None = Field(None, description="Error message if failed")


class TaskResult(BaseModel):
    """Task result storage."""

    task_id: str = Field(..., description="Unique task identifier")
    status: Literal["processing", "completed", "failed"] = Field(..., description="Final status")
    result: dict[str, Any] | None = Field(None, description="Result data if completed")
    error: str | None = Field(None, description="Error message if failed")
