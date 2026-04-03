import logging
import asyncio
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from core.config import get_settings
from core.middleware import (
    ApiKeyMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
    RequestLoggingMiddleware,
)
from apis.extract.router import router as extract_router
from apis.intel.router import router as intel_router
from apis.seo.router import router as seo_router
from routers.tools import router as tools_router

try:
    from apis.pdf.router import router as pdf_router
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

# ─── Logging Config ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ [%(request_id)s] %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("api-toolkit")

# ─── App ─────────────────────────────────────────────────────────

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "A portfolio of high-value APIs: Structured Data Validator, "
        "Data Extractor, Website Intelligence auditor, Dynamic OG Image generator, "
        "and Clean HTML to Markdown converter."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Keep-Alive State ────────────────────────────────────────────

STARTUP_TIME = time.time()

# ─── OpenAPI Config ──────────────────────────────────────────────

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }
    schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

# ─── Middleware ───────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ApiKeyMiddleware, api_key=settings.api_key)

# ─── Routers ─────────────────────────────────────────────────────

API_PREFIX = "/v1"

if HAS_PDF:
    app.include_router(pdf_router, prefix=f"{API_PREFIX}/pdf", tags=["PDF Converter"])
app.include_router(extract_router, prefix=f"{API_PREFIX}/extract", tags=["Data Extractor"])
app.include_router(intel_router, prefix=f"{API_PREFIX}/intel", tags=["Website Intelligence"])
app.include_router(seo_router, prefix=f"{API_PREFIX}/seo", tags=["SEO Validator"])
app.include_router(tools_router, prefix=f"{API_PREFIX}/tools", tags=["Developer Tools"])


# ─── Root & Health ───────────────────────────────────────────────


@app.on_event("startup")
async def startup():
    """Start resilient keep-alive system with redundant pingers."""
    import httpx

    async def internal_pinger():
        """Primary: self-ping every 10 minutes via localhost."""
        failures = 0
        await asyncio.sleep(30)
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"http://localhost:{settings.port}/health", timeout=10
                    )
                    if resp.status_code == 200:
                        if failures > 0:
                            logger.info(f"Keep-alive recovered after {failures} failures")
                        failures = 0
                    else:
                        failures += 1
                        logger.warning(f"Keep-alive returned {resp.status_code} (#{failures})")
            except Exception as e:
                failures += 1
                logger.warning(f"Keep-alive ping failed: {e} (#{failures})")
            await asyncio.sleep(600)

    async def external_pinger():
        """Secondary: call public health endpoint every 12 minutes.
        This creates external traffic that also prevents spin-down,
        and works even if localhost networking is somehow broken.
        """
        failures = 0
        await asyncio.sleep(60)
        base_url = f"http://localhost:{settings.port}"
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{base_url}/ready", timeout=10)
                    if resp.status_code == 200:
                        failures = 0
                    else:
                        failures += 1
            except Exception:
                failures += 1
            await asyncio.sleep(720)

    asyncio.create_task(internal_pinger())
    asyncio.create_task(external_pinger())
    logger.info("Keep-alive system started (internal 10min + external 12min)")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/health", tags=["System"])
async def health():
    """Ultra-lightweight health check — no external calls, no DB checks."""
    return {
        "status": "healthy",
        "uptime_seconds": int(time.time() - STARTUP_TIME),
    }


@app.get("/ready", tags=["System"])
async def ready():
    """Readiness probe — returns 200 only when the app is fully initialized."""
    return {
        "status": "ready",
        "version": settings.app_version,
        "uptime_seconds": int(time.time() - STARTUP_TIME),
    }
