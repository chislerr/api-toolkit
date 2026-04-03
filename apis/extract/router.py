from fastapi import APIRouter, HTTPException
from .service import extract_article, extract_contact, extract_product, extract_recipe
from core.models import (
    ExtractArticleRequest,
    ArticleResponse,
    ExtractContactRequest,
    ContactResponse,
    ExtractProductRequest,
    ProductResponse,
    ExtractRecipeRequest,
    RecipeResponse,
)

router = APIRouter()


@router.post(
    "/article",
    response_model=ArticleResponse,
    summary="Extract article content",
    description="Extract the main article content from a web page including title, author, date, body text, images, and metadata.",
)
async def api_extract_article(request: ExtractArticleRequest):
    try:
        result = await extract_article(request.url)
        return ArticleResponse(**result)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to extract article content")


@router.post(
    "/contact",
    response_model=ContactResponse,
    summary="Extract contact information",
    description="Extract emails, phone numbers, addresses, and social media links from a web page.",
)
async def api_extract_contact(request: ExtractContactRequest):
    try:
        result = await extract_contact(request.url)
        return ContactResponse(**result)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to extract contact information")


@router.post(
    "/product",
    response_model=ProductResponse,
    summary="Extract product details",
    description="Extract product information from e-commerce pages including name, price, images, ratings, and availability.",
)
async def api_extract_product(request: ExtractProductRequest):
    try:
        result = await extract_product(request.url)
        return ProductResponse(**result)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to extract product information")


@router.post(
    "/recipe",
    response_model=RecipeResponse,
    summary="Extract recipe data",
    description="Extract recipe information including ingredients, instructions, cooking times, nutrition, and ratings.",
)
async def api_extract_recipe(request: ExtractRecipeRequest):
    try:
        result = await extract_recipe(request.url)
        return RecipeResponse(**result)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to extract recipe information")
