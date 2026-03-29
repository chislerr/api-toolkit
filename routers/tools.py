from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

from services.og_image import generate_og_image
from services.html_to_md import extract_markdown_from_url

router = APIRouter()


class OGTemplate(str, Enum):
    BLOG = "blog"
    MINIMAL = "minimal"
    BOLD = "bold"
    CARD = "card"


class OGBackground(str, Enum):
    SOLID = "solid"
    GRADIENT = "gradient"
    GRADIENT_HORIZONTAL = "gradient_horizontal"
    GRADIENT_VERTICAL = "gradient_vertical"
    PATTERN = "pattern"
    MESH = "mesh"


class OGImageRequest(BaseModel):
    title: str = Field(..., description="The main headline for the OG image")
    subtitle: Optional[str] = Field(
        None, description="A smaller subtitle displayed below the headline"
    )
    bg_color: Optional[str] = Field(
        "#1a202c", description="Hex color code for the background"
    )
    text_color: Optional[str] = Field(
        "#ffffff", description="Hex color code for the text"
    )
    accent_color: Optional[str] = Field(
        None,
        description="Hex color for accent bar and tag pill. Auto-generated from bg_color if omitted.",
    )
    template: OGTemplate = Field(
        OGTemplate.BLOG,
        description="Layout template: blog (left-aligned, accent bar), minimal (centered, clean), bold (large title, accent bar), card (centered with card overlay)",
    )
    background: OGBackground = Field(
        OGBackground.SOLID,
        description="Background style: solid, gradient, gradient_horizontal, gradient_vertical, pattern (dots), mesh (blurred blobs)",
    )
    author: Optional[str] = Field(
        None, description="Author name displayed in the bottom meta line"
    )
    tag: Optional[str] = Field(
        None, description="Category tag displayed as a pill above the title"
    )
    domain: Optional[str] = Field(
        None, description="Domain or site name displayed in the bottom meta line"
    )
    reading_time: Optional[str] = Field(
        None,
        description="Reading time displayed in the bottom meta line (e.g. '5 min read')",
    )


class HtmlToMarkdownRequest(BaseModel):
    url: str = Field(
        ..., description="The target webpage URL to parse and convert to Markdown."
    )


@router.post(
    "/og-image",
    summary="Generate Dynamic Open Graph (OG) Image",
    description=(
        "Generate a 1200x630 OG image with templates, gradient/pattern backgrounds, "
        "accent colors, tag pills, author line, and more. "
        "Optimized for Twitter, LinkedIn, Facebook, and iMessage preview cards."
    ),
    response_class=Response,
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Returns the raw binary data of the generated PNG image.",
        }
    },
)
async def create_og_image(request: OGImageRequest):
    image_bytes = generate_og_image(
        title=request.title,
        subtitle=request.subtitle,
        bg_color=request.bg_color,
        text_color=request.text_color,
        accent_color=request.accent_color,
        template=request.template.value,
        background=request.background.value,
        author=request.author,
        tag=request.tag,
        domain=request.domain,
        reading_time=request.reading_time,
    )

    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post(
    "/html-to-markdown",
    summary="Convert Clean HTML to Markdown",
    description=(
        "Extracts the main article body from a webpage (stripping ads, nav, footers) "
        "and converts it to clean, token-efficient Markdown suitable for LLMs."
    ),
)
async def create_markdown(request: HtmlToMarkdownRequest):
    result = await extract_markdown_from_url(str(request.url))

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result
