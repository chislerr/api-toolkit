from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from core.models import PdfFromUrlRequest, PdfFromHtmlRequest
from apis.pdf.service import html_to_pdf

router = APIRouter()


@router.post(
    "/from-url",
    summary="Convert URL to PDF",
    description="Render a web page and convert it to a PDF document.",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def pdf_from_url(request: PdfFromUrlRequest):
    try:
        pdf_bytes = await html_to_pdf(
            url=request.url,
            landscape=request.landscape,
            page_size=request.page_size.value,
            margin_top=request.margin_top,
            margin_bottom=request.margin_bottom,
            margin_left=request.margin_left,
            margin_right=request.margin_right,
            print_background=request.print_background,
            header_html=request.header_html,
            footer_html=request.footer_html,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=output.pdf"},
    )


@router.post(
    "/from-html",
    summary="Convert HTML to PDF",
    description="Convert raw HTML content to a PDF document.",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def pdf_from_html(request: PdfFromHtmlRequest):
    try:
        pdf_bytes = await html_to_pdf(
            html=request.html,
            landscape=request.landscape,
            page_size=request.page_size.value,
            margin_top=request.margin_top,
            margin_bottom=request.margin_bottom,
            margin_left=request.margin_left,
            margin_right=request.margin_right,
            print_background=request.print_background,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=output.pdf"},
    )
