from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional

from services.og_image import generate_og_image
from core.middleware import verify_api_key

router = APIRouter(dependencies=[Depends(verify_api_key)])

class OGImageRequest(BaseModel):
    title: str = Field(..., description="The main headline for the OG image")
    subtitle: Optional[str] = Field(None, description="A smaller subtitle displayed below the main headline")
    bg_color: Optional[str] = Field("#1a202c", description="Hex color code for the background")
    text_color: Optional[str] = Field("#ffffff", description="Hex color code for the text")
    
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
