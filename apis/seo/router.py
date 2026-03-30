import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apis.seo.service import extract_structured_data, check_rich_results

router = APIRouter()


class SeoRequest(BaseModel):
    url: str = Field(..., description="URL to extract and validate structured data from")


@router.post(
    "/structured-data",
    summary="Extract & validate all structured data",
    description=(
        "Extract every piece of schema.org structured data from a URL: "
        "JSON-LD entities, Microdata, Open Graph tags, Twitter Cards, and meta tags. "
        "Each entity is validated against Google Rich Results requirements with "
        "field-level errors, warnings, and a completeness score."
    ),
)
async def api_structured_data(request: SeoRequest):
    try:
        result = await extract_structured_data(request.url)
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch URL: {e.response.status_code}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post(
    "/rich-results",
    summary="Check Google Rich Results eligibility",
    description=(
        "Check which Google Rich Result types a page qualifies for. "
        "Validates against 12 types: Article, Product, Recipe, FAQ, HowTo, "
        "Event, LocalBusiness, Review, BreadcrumbList, VideoObject, "
        "SoftwareApplication, Course. Returns eligible types with present fields, "
        "and ineligible types with missing required fields."
    ),
)
async def api_rich_results(request: SeoRequest):
    try:
        result = await check_rich_results(request.url)
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch URL: {e.response.status_code}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
