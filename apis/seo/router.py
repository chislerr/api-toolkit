from fastapi import APIRouter, HTTPException
from core.models import (
    SeoRequest,
    ValidateHtmlRequest,
    StructuredDataResponse,
    RichResultsResponse,
    HealthScoreResponse,
)
from apis.seo.service import (
    extract_structured_data,
    check_rich_results,
    validate_raw_html,
    compute_health_score,
)

router = APIRouter()


@router.post(
    "/structured-data",
    response_model=StructuredDataResponse,
    summary="Extract & validate all structured data",
    description=(
        "Extract every piece of schema.org structured data from a URL: "
        "JSON-LD entities, Microdata, Open Graph tags, Twitter Cards, and meta tags. "
        "Each entity is validated against Google Rich Results requirements with "
        "field-level errors, warnings, fix suggestions, and a completeness score."
    ),
)
async def api_structured_data(request: SeoRequest):
    try:
        result = await extract_structured_data(request.url)
        return StructuredDataResponse(**result)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to extract structured data")


@router.post(
    "/rich-results",
    response_model=RichResultsResponse,
    summary="Check Google Rich Results eligibility",
    description=(
        "Check which Google Rich Result types a page qualifies for. "
        "Validates against 18 types: Article, Product, Recipe, FAQ, HowTo, "
        "Event, LocalBusiness, Review, BreadcrumbList, VideoObject, "
        "SoftwareApplication, Course, Organization, Person, WebSite, "
        "WebPage, ItemList, AggregateRating. Returns eligible types with present fields, "
        "and ineligible types with missing required fields."
    ),
)
async def api_rich_results(request: SeoRequest):
    try:
        result = await check_rich_results(request.url)
        return RichResultsResponse(**result)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to check rich results eligibility")


@router.post(
    "/validate-html",
    response_model=StructuredDataResponse,
    summary="Validate structured data from raw HTML",
    description=(
        "Validate structured data directly from an HTML string without fetching a URL. "
        "Useful for testing JSON-LD snippets, templates, or CMS output before deployment. "
        "Returns the same structured extraction and validation as the URL-based endpoint."
    ),
)
async def api_validate_html(request: ValidateHtmlRequest):
    try:
        result = await validate_raw_html(request.html)
        return StructuredDataResponse(**result)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to validate HTML")


@router.post(
    "/health-score",
    response_model=HealthScoreResponse,
    summary="Structured data health score (0-100)",
    description=(
        "Get an overall structured data health score from 0 to 100 with a letter grade, "
        "detailed breakdown (JSON-LD count, Open Graph, Twitter Cards, Rich Results "
        "eligibility), and the top fix suggestions to improve your score."
    ),
)
async def api_health_score(request: SeoRequest):
    try:
        result = await compute_health_score(request.url)
        return HealthScoreResponse(**result)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to compute health score")
