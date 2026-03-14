import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from core.config import get_settings
from core.middleware import ApiKeyMiddleware, RequestLoggingMiddleware
from apis.pdf.router import router as pdf_router
from apis.extract.router import router as extract_router
from apis.intel.router import router as intel_router

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
        "A portfolio of high-value APIs: HTML/URL→PDF converter, "
        "Structured Data Extractor, and Website Intelligence auditor."
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

app.include_router(pdf_router, prefix="/pdf", tags=["PDF Converter"])
app.include_router(extract_router, prefix="/extract", tags=["Data Extractor"])
app.include_router(intel_router, prefix="/intel", tags=["Website Intelligence"])

# Import here to avoid circular dependencies if we move things, but better to import at top
from routers.tools import router as tools_router
app.include_router(tools_router, prefix="/tools", tags=["Developer Tools"])


# ─── Root & Health ───────────────────────────────────────────────


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
