"""Mockup compositing task handler."""

import base64
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from ai.exceptions import (  # type: ignore[import-not-found]
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from ai.schemas import Position  # type: ignore[import-not-found]
from providers.mockups import (  # type: ignore[import-not-found]
    MockupsProvider,
    MockupsProviderError,
    ProviderInvalidTemplateError,
)

from .base import TaskHandler, WorkerError


class MockupHandler(TaskHandler):
    """Handler for mockup compositing tasks."""

    handler_name = "mockup"

    def __init__(self) -> None:
        super().__init__()
        self.provider: MockupsProvider | None = None

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        """Validate task input data.

        Args:
            task_data: Task-specific parameters

        Raises:
            WorkerError: If validation fails
        """
        if "pattern" not in task_data:
            raise WorkerError("Missing required field: pattern")

        if "template" not in task_data and "template_id" not in task_data:
            raise WorkerError("Missing required field: template or template_id")

        if "position" not in task_data:
            raise WorkerError("Missing required field: position")

        if not isinstance(task_data["pattern"], (bytes, str)):
            raise WorkerError("pattern must be bytes or base64 string")

        if "template" in task_data and not isinstance(
            task_data["template"], (bytes, str)
        ):
            raise WorkerError("template must be bytes or base64 string")

        if not isinstance(task_data["position"], dict):
            raise WorkerError(
                "position must be a dict with x, y, scale, rotation, opacity"
            )

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Process mockup compositing task.

        Args:
            task_data: Task-specific parameters

        Returns:
            Result dict with mockup image

        Raises:
            WorkerError: If task processing fails
        """
        await self.validate_input(task_data)

        pattern_data = task_data["pattern"]
        if isinstance(pattern_data, str):
            try:
                pattern_data = base64.b64decode(pattern_data)
            except Exception as e:
                raise WorkerError(f"Invalid base64 pattern: {e}") from e

        template_data = None
        template_id = task_data.get("template_id")

        if not template_id:
            template_data = task_data["template"]
            if isinstance(template_data, str):
                try:
                    template_data = base64.b64decode(template_data)
                except Exception as e:
                    raise WorkerError(f"Invalid base64 template: {e}") from e

        try:
            position = Position(**task_data["position"])
        except Exception as e:
            raise WorkerError(f"Invalid position parameters: {e}") from e

        try:
            if self.provider is None:
                self.provider = MockupsProvider()

            mockup_bytes = await self.provider.composite_mockup(
                pattern=pattern_data,
                template=template_data or b"",
                position=position,
                template_id=template_id,
            )

            return {
                "status": "success",
                "mockup": base64.b64encode(mockup_bytes).decode("utf-8"),
            }

        except ProviderConfigurationError as e:
            self.logger.error(f"Provider configuration error: {e}")
            raise WorkerError(f"Mockups provider not configured: {e}") from e

        except ProviderTimeoutError as e:
            self.logger.warning(f"Provider timeout: {e}")
            raise WorkerError(f"Mockup compositing timed out: {e}") from e

        except ProviderRateLimitError as e:
            self.logger.warning(f"Rate limit hit: {e}")
            raise WorkerError(f"Rate limited: {e}") from e

        except ProviderInvalidTemplateError as e:
            self.logger.error(f"Invalid template or position: {e}")
            raise WorkerError(f"Invalid template or position: {e}") from e

        except MockupsProviderError as e:
            self.logger.error(f"Mockups provider error: {e}")
            raise WorkerError(f"Mockup compositing failed: {e}") from e

        except Exception as e:
            self.logger.exception("Unexpected error during mockup compositing")
            raise WorkerError(f"Unexpected error: {e}") from e
