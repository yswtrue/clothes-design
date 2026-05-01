import logging
import sys
import time
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", "-")
        return True


def configure_logging(level: int = logging.INFO) -> None:
    fmt = "%(asctime)s | %(levelname)-5s | %(request_id)s | %(name)s:%(lineno)d | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt))
    handler.addFilter(RequestContextFilter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger_name: str = "api.request"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid4())[:8])
        request.state.request_id = request_id

        start = time.perf_counter()
        method = request.method
        path = request.url.path
        query = str(request.query_params) if request.query_params else ""

        extra = {"request_id": request_id}

        self.logger.debug(
            f"→ {method} {path}{'?' + query if query else ''}",
            extra=extra,
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            self.logger.error(
                f"✗ {method} {path} | {elapsed:.0f}ms | {type(exc).__name__}: {exc}",
                extra=extra,
            )
            raise

        elapsed = (time.perf_counter() - start) * 1000
        status = response.status_code

        if status >= 500:
            log = self.logger.error
            symbol = "✗"
        elif status >= 400:
            log = self.logger.warning
            symbol = "⚠"
        else:
            log = self.logger.info
            symbol = "✓"

        log(f"{symbol} {method} {path} | {status} | {elapsed:.0f}ms", extra=extra)

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
