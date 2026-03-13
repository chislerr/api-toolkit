from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ─── Shared Response Models ───────────────────────────────────────


class StatusResponse(BaseModel):
    status: str = "ok"
    message: str = ""


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""


# ─── PDF API Models ──────────────────────────────────────────────


class PageSize(str, Enum):
    A4 = "A4"
    LETTER = "Letter"
    LEGAL = "Legal"
    A3 = "A3"
    TABLOID = "Tabloid"


class PdfFromUrlRequest(BaseModel):
    url: str = Field(..., description="URL to convert to PDF")
    landscape: bool = Field(False, description="Landscape orientation")
    page_size: PageSize = Field(PageSize.A4, description="Page size format")
    margin_top: str = Field("10mm", description="Top margin")
    margin_bottom: str = Field("10mm", description="Bottom margin")
    margin_left: str = Field("10mm", description="Left margin")
    margin_right: str = Field("10mm", description="Right margin")
    print_background: bool = Field(True, description="Print background graphics")
    header_html: Optional[str] = Field(None, description="Custom header HTML")
    footer_html: Optional[str] = Field(None, description="Custom footer HTML")


class PdfFromHtmlRequest(BaseModel):
    html: str = Field(..., description="HTML content to convert to PDF")
    landscape: bool = False
    page_size: PageSize = PageSize.A4
    margin_top: str = "10mm"
    margin_bottom: str = "10mm"
    margin_left: str = "10mm"
    margin_right: str = "10mm"
    print_background: bool = True


# ─── Extract API Models ──────────────────────────────────────────


class ExtractArticleRequest(BaseModel):
    url: str = Field(..., description="URL of the article to extract")


class ArticleResponse(BaseModel):
    title: str = ""
    author: str = ""
    date: str = ""
    body: str = ""
    images: list[str] = []
    word_count: int = 0
    source_url: str = ""


class ExtractContactRequest(BaseModel):
    url: str = Field(..., description="URL to extract contact info from")


class ContactResponse(BaseModel):
    emails: list[str] = []
    phones: list[str] = []
    addresses: list[str] = []
    social_links: dict[str, str] = {}
    source_url: str = ""


class ExtractProductRequest(BaseModel):
    url: str = Field(..., description="Product page URL")


class ProductResponse(BaseModel):
    name: str = ""
    price: str = ""
    currency: str = ""
    description: str = ""
    images: list[str] = []
    sku: str = ""
    availability: str = ""
    source_url: str = ""


class CustomExtractionRequest(BaseModel):
    url: str = Field(..., description="URL to extract data from")
    schema_definition: dict = Field(
        ..., description="JSON schema defining the data structure to extract"
    )
    prompt: str = Field(
        "", description="Additional context for the extraction"
    )


# ─── Intel API Models ────────────────────────────────────────────


class IntelAuditRequest(BaseModel):
    url: str = Field(..., description="URL to audit")


class MetaTags(BaseModel):
    title: str = ""
    description: str = ""
    canonical: str = ""
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    twitter_card: str = ""


class SecurityHeaders(BaseModel):
    has_hsts: bool = False
    has_csp: bool = False
    has_x_frame_options: bool = False
    has_x_content_type: bool = False
    has_referrer_policy: bool = False
    score: str = ""  # "A", "B", "C", "D", "F"
    details: dict[str, str] = {}


class PerformanceMetrics(BaseModel):
    page_size_bytes: int = 0
    page_size_readable: str = ""
    load_time_ms: int = 0
    num_requests: int = 0


class IntelAuditResponse(BaseModel):
    url: str
    meta_tags: MetaTags = MetaTags()
    tech_stack: list[str] = []
    security_headers: SecurityHeaders = SecurityHeaders()
    performance: PerformanceMetrics = PerformanceMetrics()
    broken_links: list[str] = []
    is_mobile_friendly: bool = False
    source_url: str = ""
