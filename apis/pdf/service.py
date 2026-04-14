import logging
from io import BytesIO
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from core.ssrf import validate_url

logger = logging.getLogger("api.pdf")

_browser = None
_playwright = None


async def _get_browser():
    """Get or create a shared browser instance for PDF generation."""
    global _browser, _playwright
    if _browser is None or not _browser.is_connected():
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=True)
        logger.info("Browser instance launched for PDF service")
    return _browser


def _is_allowed_resource_url(resource_url: str) -> bool:
    scheme = urlparse(resource_url).scheme.lower()
    if scheme in {"", "about", "data", "blob"}:
        return True
    validate_url(resource_url)
    return True


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
    Convert HTML or a URL to PDF using Playwright / headless Chromium.
    Returns raw PDF bytes.
    """
    browser = await _get_browser()
    context = await browser.new_context(viewport={"width": 1280, "height": 720})
    page = await context.new_page()

    async def route_handler(route):
        try:
            _is_allowed_resource_url(route.request.url)
            await route.continue_()
        except Exception:
            logger.warning("Blocked unsafe resource request during PDF render: %s", route.request.url)
            await route.abort()

    await page.route("**/*", route_handler)

    try:
        if url:
            validate_url(url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=5_000)
            except PlaywrightTimeoutError:
                logger.info("Continuing PDF render after network idle timeout for %s", url)
        elif html:
            await page.set_content(html, wait_until="load", timeout=15_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=3_000)
            except PlaywrightTimeoutError:
                logger.info("Continuing PDF render after HTML network idle timeout")
        else:
            raise ValueError("Either 'url' or 'html' must be provided")

        await page.emulate_media(media="screen")

        pdf_options = {
            "format": page_size,
            "landscape": landscape,
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
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("Timed out while rendering the page to PDF") from exc
    except PlaywrightError as exc:
        raise RuntimeError(f"PDF rendering failed: {exc}") from exc
    finally:
        await context.close()


async def merge_pdfs(pdf_list: list[bytes]) -> bytes:
    """Merge multiple PDF byte arrays into a single PDF."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()

    for pdf_bytes in pdf_list:
        reader = PdfReader(BytesIO(pdf_bytes))
        for page_obj in reader.pages:
            writer.add_page(page_obj)

    output = BytesIO()
    writer.write(output)
    result = output.getvalue()
    logger.info("Merged %d PDFs -> %d bytes", len(pdf_list), len(result))
    return result
