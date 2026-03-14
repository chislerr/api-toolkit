from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional

from services.og_image import generate_og_image
from services.html_to_md import extract_markdown_from_url
from core.middleware import verify_api_key

router = APIRouter(dependencies=[Depends(verify_api_key)])

class OGImageRequest(BaseModel):
    title: str = Field(..., description="The main headline for the OG image")
    subtitle: Optional[str] = Field(None, description="A smaller subtitle displayed below the main headline")
    bg_color: Optional[str] = Field("#1a202c", description="Hex color code for the background")
    text_color: Optional[str] = Field("#ffffff", description="Hex color code for the text")

class HtmlToMarkdownRequest(BaseModel):
    url: HttpUrl = Field(..., description="The target webpage URL to parse and convert to Markdown.")
    
@router.post(
    "/og-image",
    summary="Generate Dynamic Open Graph (OG) Image",
    description="Generates a static 1200x630 OG image perfectly formatted for Twitter, LinkedIn, and iMessage preview cards.",
    response_class=Response,
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Returns the raw binary data of the generated PNG image.",
        }
    },
)
async def create_og_image(request: OGImageRequest):
    """
    Generates an OG image and returns it as a raw PNG response.
    """
    image_bytes = generate_og_image(
        title=request.title,
        subtitle=request.subtitle,
        bg_color=request.bg_color,
        text_color=request.text_color
    )
    
    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400" # Cache the image for 24 hours
        }
    )

@router.post(
    "/html-to-markdown",
    summary="Convert Clean HTML to Markdown",
    description="Extracts the main article body from a webpage (stripping ads, nav, footers) and converts it to clean, token-efficient Markdown suitable for LLMs.",
)
async def create_markdown(request: HtmlToMarkdownRequest):
    """
    Takes a URL, uses readability to clean the HTML, and markdownify to convert to MD.
    """
    result = await extract_markdown_from_url(str(request.url))
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return result
