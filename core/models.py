from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
from urllib.parse import urlparse
import re


def _validate_url(value: str) -> str:
    """Shared URL validator for Pydantic models."""
    if len(value) > 2048:
        raise ValueError("URL must not exceed 2048 characters")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must start with http:// or https://")
    if not parsed.hostname:
        raise ValueError("URL must contain a valid hostname")
    return value


MARGIN_PATTERN = re.compile(r"^\d+(?:\.\d+)?(?:mm|cm|in|px)$")


def _validate_margin(value: str) -> str:
    if not MARGIN_PATTERN.fullmatch(value.strip()):
        raise ValueError("Margin values must look like '10mm', '0.5in', '12px', or '1cm'")
    return value


# ─── Shared Response Models ───────────────────────────────────────


class StatusResponse(BaseModel):
    status: str = "ok"
    message: str = ""


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
    request_id: str = ""


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

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_url(v)

    @field_validator("margin_top", "margin_bottom", "margin_left", "margin_right")
    @classmethod
    def validate_margin(cls, v: str) -> str:
        return _validate_margin(v)


class PdfFromHtmlRequest(BaseModel):
    html: str = Field(..., description="HTML content to convert to PDF", max_length=5_000_000)
    landscape: bool = False
    page_size: PageSize = PageSize.A4
    margin_top: str = "10mm"
    margin_bottom: str = "10mm"
    margin_left: str = "10mm"
    margin_right: str = "10mm"
    print_background: bool = True

    @field_validator("margin_top", "margin_bottom", "margin_left", "margin_right")
    @classmethod
    def validate_margin(cls, v: str) -> str:
        return _validate_margin(v)


# ─── Extract API Models ──────────────────────────────────────────


class ExtractArticleRequest(BaseModel):
    url: str = Field(..., description="URL of the article to extract")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_url(v)


class ArticleResponse(BaseModel):
    title: str = ""
    author: str = ""
    date: str = ""
    body: str = ""
    images: list[str] = []
    word_count: int = 0
    language: str = ""
    source_url: str = ""
    confidence: dict = {}


class ExtractContactRequest(BaseModel):
    url: str = Field(..., description="URL to extract contact info from")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_url(v)


class ContactResponse(BaseModel):
    emails: list[str] = []
    phones: list[str] = []
    addresses: list[str] = []
    social_links: dict[str, str] = {}
    source_url: str = ""
    confidence: dict = {}


class ExtractProductRequest(BaseModel):
    url: str = Field(..., description="Product page URL")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_url(v)


class ProductResponse(BaseModel):
    name: str = ""
    price: str = ""
    currency: str = ""
    description: str = ""
    images: list[str] = []
    sku: str = ""
    brand: str = ""
    availability: str = ""
    rating: Optional[float] = None
    review_count: Optional[int] = None
    source_url: str = ""
    extraction_method: str = ""
    confidence: dict = {}


class ExtractRecipeRequest(BaseModel):
    url: str = Field(..., description="Recipe page URL")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_url(v)


class RecipeResponse(BaseModel):
    name: str = ""
    description: str = ""
    author: str = ""
    prep_time: str = ""
    cook_time: str = ""
    total_time: str = ""
    servings: str = ""
    ingredients: list[str] = []
    instructions: list[str] = []
    images: list[str] = []
    cuisine: str = ""
    category: str = ""
    calories: str = ""
    rating: Optional[float] = None
    review_count: Optional[int] = None
    source_url: str = ""
    extraction_method: str = ""
    confidence: dict = {}


# ─── Intel API Models ────────────────────────────────────────────


class IntelAuditRequest(BaseModel):
    url: str = Field(..., description="URL to audit")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_url(v)


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
    score: str = ""
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


# ─── SEO / Structured Data Validator Models ───────────────────────


class SeoRequest(BaseModel):
    url: str = Field(..., description="URL to extract and validate structured data from")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_url(v)


class ValidateHtmlRequest(BaseModel):
    html: str = Field(..., description="Raw HTML content to validate for structured data", max_length=5_000_000)


class ValidationIssue(BaseModel):
    field: str = ""
    message: str = ""
    severity: str = ""
    fix: str = ""


class EntityValidation(BaseModel):
    type: str = ""
    rich_result_category: Optional[str] = None
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    score: Optional[float] = None


class StructuredDataSummary(BaseModel):
    total_entities: int = 0
    types_found: list[str] = []
    rich_results_eligible: list[str] = []
    overall_score: float = 0.0
    critical_errors: int = 0
    warnings: int = 0


class StructuredDataResponse(BaseModel):
    url: str
    json_ld: list[dict] = []
    microdata: list[dict] = []
    open_graph: dict = {}
    twitter_card: dict = {}
    meta_tags: dict = {}
    summary: StructuredDataSummary = StructuredDataSummary()
    source_url: str = ""


class RichResultEntry(BaseModel):
    type: str
    status: str
    fields_present: list[str] = []
    fields_missing: list[str] = []
    fields_recommended: list[str] = []


class RichResultsSummary(BaseModel):
    eligible_count: int = 0
    total_types_checked: int = 0
    types_checked: list[str] = []


class RichResultsResponse(BaseModel):
    url: str
    eligible: list[RichResultEntry] = []
    not_eligible: list[RichResultEntry] = []
    summary: RichResultsSummary = RichResultsSummary()
    source_url: str = ""


class HealthScoreBreakdown(BaseModel):
    structured_data_present: bool = False
    json_ld_count: int = 0
    microdata_count: int = 0
    has_open_graph: bool = False
    has_twitter_card: bool = False
    rich_results_eligible: int = 0
    rich_results_total: int = 0
    critical_errors: int = 0
    warnings: int = 0


class HealthScoreResponse(BaseModel):
    url: str
    score: int = 0
    grade: str = ""
    breakdown: HealthScoreBreakdown = HealthScoreBreakdown()
    top_fixes: list[str] = []
    source_url: str = ""


# ─── Developer Tools Models ──────────────────────────────────────


class OgImageRequest(BaseModel):
    title: str = Field(..., description="Main headline for the OG image", max_length=200)
    subtitle: Optional[str] = Field(None, description="Subtitle text", max_length=300)
    bg_color: str = Field("#1a202c", description="Hex background color")
    text_color: str = Field("#ffffff", description="Hex text color")
    accent_color: Optional[str] = Field(None, description="Hex accent color")
    template: str = Field("blog", description="Template: blog, minimal, bold, card")
    background: str = Field("solid", description="Background: solid, gradient, gradient_horizontal, gradient_vertical, pattern, mesh")
    author: Optional[str] = Field(None, description="Author name", max_length=100)
    tag: Optional[str] = Field(None, description="Tag/label pill text", max_length=50)
    domain: Optional[str] = Field(None, description="Domain name to display", max_length=100)
    reading_time: Optional[str] = Field(None, description="Reading time label", max_length=50)


class HtmlToMarkdownRequest(BaseModel):
    url: str = Field(..., description="URL to convert to Markdown")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_url(v)


class HtmlToMarkdownResponse(BaseModel):
    title: str = ""
    markdown: str = ""
    character_count: int = 0
    readability_success: bool = False
