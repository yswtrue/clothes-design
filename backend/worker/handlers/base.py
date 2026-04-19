"""Task handler base class and registry."""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class WorkerError(Exception):
    """Base worker error."""

    pass


class TaskHandler(ABC):
    """Abstract base class for task handlers."""

    handler_name: str

    def __init__(self) -> None:
        """Initialize handler."""
        self.logger = logging.getLogger(f"worker.handlers.{self.handler_name}")

    @abstractmethod
    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Process task and return result.

        Args:
            task_data: Task-specific parameters

        Returns:
            Result dict with task output

        Raises:
            Exception: Any error during task processing is caught and logged
        """

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        """Validate task input data.

        Override in subclasses to add validation.
        Raise WorkerError if validation fails.
        """


class HandlerRegistry:
    """Registry for task handlers."""

    def __init__(self) -> None:
        """Initialize registry."""
        self._handlers: dict[str, type[TaskHandler]] = {}

    def register(self, task_type: str, handler_class: type[TaskHandler]) -> None:
        """Register handler for task type.

        Args:
            task_type: Task type identifier
            handler_class: Handler class (not instance)
        """
        self._handlers[task_type] = handler_class
        logger.info(f"Registered handler for task_type={task_type}")

    def get(self, task_type: str) -> TaskHandler | None:
        """Get handler instance for task type.

        Args:
            task_type: Task type identifier

        Returns:
            Handler instance or None if not found
        """
        handler_class = self._handlers.get(task_type)
        if handler_class:
            return handler_class()
        return None

    def list_handlers(self) -> list[str]:
        """List all registered task types.

        Returns:
            List of task type strings
        """
        return list(self._handlers.keys())


__all__ = ["HandlerRegistry", "TaskHandler", "WorkerError"]
