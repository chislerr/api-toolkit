import logging
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from core.config import get_settings
from core.middleware import ApiKeyMiddleware, RequestLoggingMiddleware
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
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)

# ─── App ─────────────────────────────────────────────────────────

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "A portfolio of high-value APIs: Structured Data Extractor, "
        "Website Intelligence auditor, Dynamic OG Image generator, "
        "and Clean HTML to Markdown converter."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)


# Add API Key to Swagger UI "Authorize" button
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
    return schema


app.openapi = custom_openapi

# ─── Middleware ───────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ApiKeyMiddleware)

# ─── Routers ─────────────────────────────────────────────────────

if HAS_PDF:
    app.include_router(pdf_router, prefix="/pdf", tags=["PDF Converter"])
app.include_router(extract_router, prefix="/extract", tags=["Data Extractor"])
app.include_router(intel_router, prefix="/intel", tags=["Website Intelligence"])
app.include_router(seo_router, prefix="/seo", tags=["SEO Validator"])
app.include_router(tools_router, prefix="/tools", tags=["Developer Tools"])


# ─── Root & Health ───────────────────────────────────────────────


@app.on_event("startup")
async def start_keep_alive():
    """Self-ping every 13 minutes to prevent Render free tier spin-down."""
    import httpx

    async def ping():
        while True:
            await asyncio.sleep(780)  # 13 minutes
            try:
                async with httpx.AsyncClient() as client:
                    await client.get(
                        f"http://localhost:{settings.port}/health", timeout=5
                    )
            except Exception:
                pass

    asyncio.create_task(ping())


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy"}
