import time
import logging
import uuid
from collections import defaultdict
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from core.config import get_settings

logger = logging.getLogger("api-toolkit.middleware")

# ─── Rate Limiter (Sliding Window) ────────────────────────────────

class RateLimiter:
    """In-memory sliding window rate limiter keyed by API key."""

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds

        self.requests[key] = [
            ts for ts in self.requests[key] if ts > cutoff
        ]

        if len(self.requests[key]) >= self.max_requests:
            return False

        self.requests[key].append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.time()
        cutoff = now - self.window_seconds
        active = [ts for ts in self.requests[key] if ts > cutoff]
        return max(0, self.max_requests - len(active))


_settings = get_settings()
rate_limiter = RateLimiter(max_requests=_settings.rate_limit)


# ─── API Key Middleware ──────────────────────────────────────────

class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Validates X-API-Key header on protected routes."""

    def __init__(self, app, api_key: str):
        super().__init__(app)
        self.api_key = api_key
        self.public_paths = {"/", "/health", "/ready", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.public_paths:
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key", "")
        if not provided_key or provided_key != self.api_key:
            return Response(
                status_code=401,
                content='{"error": "unauthorized", "detail": "Valid X-API-Key header required"}',
                media_type="application/json",
            )

        return await call_next(request)


# ─── Rate Limit Middleware ───────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforces per-API-key rate limits."""

    PUBLIC_PATHS = {"/", "/health", "/ready", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "anonymous")

        if not rate_limiter.is_allowed(api_key):
            return Response(
                status_code=429,
                content='{"error": "rate_limited", "detail": "Too many requests. Please slow down and try again later."}',
                media_type="application/json",
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(rate_limiter.remaining(api_key))
        return response


# ─── Request ID Middleware ───────────────────────────────────────

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Adds X-Request-ID to every request/response for tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ─── Request Logging Middleware ──────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000
        request_id = getattr(request.state, "request_id", "unknown")

        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"-> {response.status_code} ({duration_ms:.0f}ms)"
        )

        return response
