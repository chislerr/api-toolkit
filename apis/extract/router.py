from fastapi import APIRouter, HTTPException
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
from apis.extract.service import (
    extract_article,
    extract_contact,
    extract_product,
    extract_recipe,
)

router = APIRouter()


@router.post(
    "/article",
    response_model=ArticleResponse,
    summary="Extract article content",
    description="Extract title, author, date, body text, images, language, and confidence scores from any article or blog post URL.",
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
    description="Extract emails, phone numbers, physical addresses, and social media links from any URL. Includes confidence scores per field.",
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
    description=(
        "Extract product name, price, description, images, SKU, brand, rating, "
        "review count, and availability from any product page. Uses JSON-LD "
        "structured data when available, falls back to microdata then heuristics. "
        "Returns extraction method used and confidence scores."
    ),
)
async def api_extract_product(request: ExtractProductRequest):
    try:
        result = await extract_product(request.url)
        return ProductResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post(
    "/recipe",
    response_model=RecipeResponse,
    summary="Extract recipe data",
    description=(
        "Extract structured recipe data from any recipe page: name, ingredients, "
        "step-by-step instructions, prep/cook/total time, servings, cuisine, "
        "calories, rating, and images. Parses schema.org Recipe JSON-LD. "
        "Returns confidence scores per field."
    ),
)
async def api_extract_recipe(request: ExtractRecipeRequest):
    try:
        result = await extract_recipe(request.url)
        return RecipeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
