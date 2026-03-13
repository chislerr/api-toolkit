import logging
from playwright.async_api import async_playwright

logger = logging.getLogger("api.pdf")

# Reusable browser instance (created on first call)
_browser = None


async def _get_browser():
    """Get or create a shared browser instance for PDF generation."""
    global _browser
    if _browser is None or not _browser.is_connected():
        pw = await async_playwright().start()
        _browser = await pw.chromium.launch(headless=True)
        logger.info("Browser instance launched for PDF service")
    return _browser


async def html_to_pdf(
    html: str = "",
    url: str = "",
    landscape: bool = False,
    page_size: str = "A4",
    margin_top: str = "10mm",
    margin_bottom: str = "10mm",
    margin_left: str = "10mm",
    margin_right: str = "10mm",
    print_background: bool = True,
    header_html: str | None = None,
    footer_html: str | None = None,
) -> bytes:
    """
    Convert HTML string or URL to PDF using Playwright / headless Chromium.
    Returns raw PDF bytes.
    """
    browser = await _get_browser()
    page = await browser.new_page()

    try:
        if url:
            await page.goto(url, wait_until="networkidle", timeout=30_000)
        elif html:
            await page.set_content(html, wait_until="networkidle", timeout=15_000)
        else:
            raise ValueError("Either 'url' or 'html' must be provided")

        # Page size dimensions (width x height in inches)
        page_sizes = {
            "A4": {"width": "8.27in", "height": "11.69in"},
            "Letter": {"width": "8.5in", "height": "11in"},
            "Legal": {"width": "8.5in", "height": "14in"},
            "A3": {"width": "11.69in", "height": "16.54in"},
            "Tabloid": {"width": "11in", "height": "17in"},
        }

        size = page_sizes.get(page_size, page_sizes["A4"])

        pdf_options = {
            "landscape": landscape,
            "width": size["width"],
            "height": size["height"],
            "margin": {
                "top": margin_top,
                "bottom": margin_bottom,
                "left": margin_left,
                "right": margin_right,
            },
            "print_background": print_background,
        }

        if header_html:
            pdf_options["header_template"] = header_html
            pdf_options["display_header_footer"] = True

        if footer_html:
            pdf_options["footer_template"] = footer_html
            pdf_options["display_header_footer"] = True

        pdf_bytes = await page.pdf(**pdf_options)
        logger.info("PDF generated: %d bytes (source=%s)", len(pdf_bytes), url or "html")
        return pdf_bytes

    finally:
        await page.close()


async def merge_pdfs(pdf_list: list[bytes]) -> bytes:
    """Merge multiple PDF byte arrays into a single PDF."""
    from pypdf import PdfReader, PdfWriter
    from io import BytesIO

    writer = PdfWriter()

    for pdf_bytes in pdf_list:
        reader = PdfReader(BytesIO(pdf_bytes))
        for page_obj in reader.pages:
            writer.add_page(page_obj)

    output = BytesIO()
    writer.write(output)
    result = output.getvalue()
    logger.info("Merged %d PDFs → %d bytes", len(pdf_list), len(result))
    return result
