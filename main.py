import asyncio
import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from apis.extract.router import router as extract_router
from apis.intel.router import router as intel_router
from apis.seo.router import router as seo_router
from core.config import get_settings
from core.middleware import (
    ApiKeyMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
    RequestLoggingMiddleware,
)
from routers.tools import router as tools_router

try:
    from apis.pdf.router import router as pdf_router

    HAS_PDF = True
except ImportError:
    HAS_PDF = False


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | [%(request_id)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("api-toolkit")

settings = get_settings()
STARTUP_TIME = time.time()
API_PREFIX = "/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    async def internal_pinger():
        failures = 0
        await asyncio.sleep(30)
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{settings.keep_alive_public_url}/health", timeout=15)
                if response.status_code == 200:
                    if failures > 0:
                        logger.info("Keep-alive recovered after %d failures", failures)
                    failures = 0
                else:
                    failures += 1
                    logger.warning("Keep-alive returned %d (#%d)", response.status_code, failures)
            except Exception as exc:
                failures += 1
                logger.warning("Keep-alive ping failed: %s (#%d)", exc, failures)
            await asyncio.sleep(600)

    async def external_pinger():
        failures = 0
        await asyncio.sleep(60)
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{settings.keep_alive_public_url}/health", timeout=15)
                if response.status_code == 200:
                    failures = 0
                else:
                    failures += 1
                    logger.warning("External keep-alive returned %d (#%d)", response.status_code, failures)
            except Exception as exc:
                failures += 1
                logger.warning("External keep-alive failed: %s (#%d)", exc, failures)
            await asyncio.sleep(720)

    tasks = []
    if settings.keep_alive_enabled and settings.keep_alive_public_url:
        tasks = [
            asyncio.create_task(internal_pinger()),
            asyncio.create_task(external_pinger()),
        ]
        logger.info("Keep-alive system started (internal 10min + external 12min)")

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


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
    lifespan=lifespan,
)


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
        "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
    }
    schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

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

if HAS_PDF:
    app.include_router(pdf_router, prefix=f"{API_PREFIX}/pdf", tags=["PDF Converter"])
app.include_router(extract_router, prefix=f"{API_PREFIX}/extract", tags=["Data Extractor"])
app.include_router(intel_router, prefix=f"{API_PREFIX}/intel", tags=["Website Intelligence"])
app.include_router(seo_router, prefix=f"{API_PREFIX}/seo", tags=["SEO Validator"])
app.include_router(tools_router, prefix=f"{API_PREFIX}/tools", tags=["Developer Tools"])


@app.get("/", include_in_schema=False)
async def root():
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}


@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy", "uptime_seconds": int(time.time() - STARTUP_TIME)}


@app.get("/ready", tags=["System"])
async def ready():
    return {
        "status": "ready",
        "version": settings.app_version,
        "uptime_seconds": int(time.time() - STARTUP_TIME),
    }
