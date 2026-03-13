from fastapi import APIRouter, HTTPException
from core.models import (
    ExtractArticleRequest, ArticleResponse,
    ExtractContactRequest, ContactResponse,
    ExtractProductRequest, ProductResponse,
)
from apis.extract.service import extract_article, extract_contact, extract_product

router = APIRouter()


@router.post(
    "/article",
    response_model=ArticleResponse,
    summary="Extract article content",
    description="Extract title, author, date, body text, and images from any article or blog post URL.",
)
async def api_extract_article(request: ExtractArticleRequest):
    try:
        result = await extract_article(request.url)
        return ArticleResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post(
    "/contact",
    response_model=ContactResponse,
    summary="Extract contact information",
    description="Extract emails, phone numbers, physical addresses, and social media links from any URL.",
)
async def api_extract_contact(request: ExtractContactRequest):
    try:
        result = await extract_contact(request.url)
        return ContactResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post(
    "/product",
    response_model=ProductResponse,
    summary="Extract product data",
    description="Extract product name, price, description, images, and SKU from any product page. Uses JSON-LD structured data when available, falls back to heuristics.",
)
async def api_extract_product(request: ExtractProductRequest):
    try:
        result = await extract_product(request.url)
        return ProductResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
