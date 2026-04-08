"""Worker main process for task queue consumption."""

import asyncio
import logging
import signal
from typing import Any

from backend.task_queue import (
    dequeue_task,
    get_task_status,
    update_task_status,
    QueueError,
)

from .handlers import HandlerRegistry, WorkerError
from .handlers.analyze import AnalyzeHandler
from .handlers.export_pattern import ExportPatternHandler
from .handlers.generate import GenerateHandler
from .handlers.mockup import MockupHandler
from .handlers.upscale import UpscaleHandler
from .handlers.vectorize import VectorizeHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

TASK_TIMEOUT = 300
MAX_RETRIES = 3
DEQUEUE_TIMEOUT = 1


class Worker:
    """Task queue worker process."""

    def __init__(self) -> None:
        """Initialize worker."""
        self.handler_registry = HandlerRegistry()
        self.running = True
        self.current_task: str | None = None

    def register_handler(self, task_type: str, handler_class: type) -> None:
        """Register handler for task type."""
        self.handler_registry.register(task_type, handler_class)
        logger.info(f"Registered handler for task_type={task_type}")

    def setup_signal_handlers(self) -> None:
        """Setup SIGTERM and SIGINT handlers for graceful shutdown."""

        def handle_shutdown(signum: int, frame: Any) -> None:
            signal_name = signal.Signals(signum).name
            logger.info(f"Received {signal_name}, initiating graceful shutdown...")
            self.running = False

        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)

    async def process_task(self, task_id: str) -> bool:
        """Process single task with retry logic.

        Args:
            task_id: Task ID to process

        Returns:
            True if succeeded, False if failed after max retries
        """
        retry_count = 0

        while retry_count < MAX_RETRIES:
            try:
                status = await get_task_status(task_id)
                if not status:
                    logger.error(f"Task {task_id} not found")
                    return False

                logger.info(
                    f"Processing task {task_id} (type={status.task_type}, attempt={retry_count + 1})"
                )

                await update_task_status(task_id, "processing")

                handler = self.handler_registry.get(status.task_type)
                if not handler:
                    error_msg = f"No handler for task_type={status.task_type}"
                    logger.error(error_msg)
                    await update_task_status(task_id, "failed", error=error_msg)
                    return False

                await handler.validate_input(status.data)

                try:
                    result = await asyncio.wait_for(
                        handler.handle(status.data), timeout=TASK_TIMEOUT
                    )
                    await update_task_status(task_id, "completed", result=result)
                    logger.info(f"Task {task_id} completed successfully")
                    return True

                except asyncio.TimeoutError:
                    error_msg = f"Task {task_id} timed out after {TASK_TIMEOUT}s"
                    logger.warning(error_msg)
                    retry_count += 1
                    if retry_count >= MAX_RETRIES:
                        await update_task_status(task_id, "failed", error=error_msg)
                        return False
                    await asyncio.sleep(2**retry_count)

            except WorkerError as exc:
                error_msg = str(exc)
                logger.error(f"Worker error processing task {task_id}: {error_msg}")
                await update_task_status(task_id, "failed", error=error_msg)
                return False
            except QueueError as exc:
                error_msg = f"Queue error: {exc}"
                logger.error(error_msg)
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    return False
                await asyncio.sleep(2**retry_count)
            except Exception as exc:
                error_msg = f"Unexpected error: {exc}"
                logger.exception(error_msg)
                await update_task_status(task_id, "failed", error=error_msg)
                return False

        logger.error(f"Task {task_id} failed after {MAX_RETRIES} retries")
        return False

    async def run(self) -> None:
        """Main worker loop."""
        self.setup_signal_handlers()
        logger.info("Worker started, listening for tasks...")

        try:
            while self.running:
                try:
                    task_id = await dequeue_task(timeout=DEQUEUE_TIMEOUT)

                    if task_id:
                        self.current_task = task_id
                        await self.process_task(task_id)
                        self.current_task = None
                    else:
                        await asyncio.sleep(0.1)

                except KeyboardInterrupt:
                    logger.info("Keyboard interrupt received")
                    self.running = False
                except Exception as exc:
                    logger.exception(f"Error in worker loop: {exc}")
                    await asyncio.sleep(1)

        finally:
            logger.info("Worker shutdown complete")


async def main() -> None:
    """Main entry point."""
    worker = Worker()

    logger.info("Initializing worker...")

    worker.register_handler("analyze", AnalyzeHandler)
    worker.register_handler("generate", GenerateHandler)
    worker.register_handler("mockup", MockupHandler)
    worker.register_handler("upscale", UpscaleHandler)
    worker.register_handler("vectorize", VectorizeHandler)
    worker.register_handler("export_pattern", ExportPatternHandler)

    logger.info("Worker ready to process tasks")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
