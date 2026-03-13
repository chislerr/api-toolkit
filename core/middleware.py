import time
import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from core.config import get_settings

logger = logging.getLogger("api")


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Validate API key from X-API-Key header on all non-docs routes."""

    SKIP_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        settings = get_settings()
        api_key = request.headers.get("X-API-Key", "")

        if not api_key or api_key != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API key", "detail": "Provide a valid X-API-Key header"},
            )

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with timing information."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "%s %s → %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"
        return response
