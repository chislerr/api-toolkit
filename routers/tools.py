from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from core.models import OgImageRequest, HtmlToMarkdownRequest, HtmlToMarkdownResponse
from services.og_image import generate_og_image
from services.html_to_md import extract_markdown_from_url

router = APIRouter()


@router.post(
    "/og-image",
    summary="Generate Dynamic OG Image",
    description=(
        "Generate a 1200x630 Open Graph image with customizable templates, "
        "backgrounds, and styling. Returns a raw PNG image."
    ),
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def og_image(request: OgImageRequest):
    try:
        image_bytes = generate_og_image(
            title=request.title,
            subtitle=request.subtitle,
            bg_color=request.bg_color,
            text_color=request.text_color,
            accent_color=request.accent_color,
            template=request.template,
            background=request.background,
            author=request.author,
            tag=request.tag,
            domain=request.domain,
            reading_time=request.reading_time,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate OG image")

    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={"Cache-Control": "max-age=86400"},
    )


@router.post(
    "/html-to-markdown",
    response_model=HtmlToMarkdownResponse,
    summary="Convert HTML to Markdown",
    description=(
        "Fetch a webpage, extract the main content using readability, and convert "
        "it to clean, token-efficient Markdown. Ideal for LLM context preparation."
    ),
)
async def html_to_markdown(request: HtmlToMarkdownRequest):
    try:
        result = await extract_markdown_from_url(request.url)

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return HtmlToMarkdownResponse(**result)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to convert HTML to Markdown")
