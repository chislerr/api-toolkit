import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from fastapi import HTTPException
from markdownify import markdownify as md
from readability import Document

from core.fetch import fetch_html
from core.ssrf import validate_url

REMOVE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "svg",
    "form",
    "button",
    "input",
    "nav",
    "footer",
    "header",
    "aside",
    "[role='navigation']",
    "[role='contentinfo']",
]
FALLBACK_SELECTORS = [
    "article",
    "main",
    "[role='main']",
    ".article-content",
    ".post-content",
    ".entry-content",
    ".content",
]


def _remove_boilerplate(soup: BeautifulSoup) -> None:
    for selector in REMOVE_SELECTORS:
        for element in soup.select(selector):
            element.decompose()


def _fallback_content(page_soup: BeautifulSoup) -> str:
    for selector in FALLBACK_SELECTORS:
        element = page_soup.select_one(selector)
        if element:
            return str(element)
    return str(page_soup.body or page_soup)


def _absolutize_links(soup: BeautifulSoup, base_url: str) -> None:
    for link in soup.find_all("a", href=True):
        link["href"] = urljoin(base_url, link["href"])
    for image in soup.find_all("img", src=True):
        image["src"] = urljoin(base_url, image["src"])


def _clean_fragment(fragment_html: str, base_url: str) -> str:
    soup = BeautifulSoup(fragment_html, "html.parser")
    _remove_boilerplate(soup)
    _absolutize_links(soup, base_url)
    return str(soup)


def _normalize_markdown(markdown_text: str, title: str) -> str:
    normalized = markdown_text.replace("\r\n", "\n")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized).strip()
    if title:
        title_heading = f"# {title}"
        if normalized.startswith(f"{title_heading}\n"):
            normalized = normalized[len(title_heading) :].lstrip()
    return normalized


async def extract_markdown_from_url(url: str) -> dict:
    """
    Fetch HTML from a URL, extract the main content, and convert it to Markdown.
    """
    validate_url(url)

    try:
        fetched = await fetch_html(url, timeout=20.0)
    except HTTPException:
        raise
    except Exception as exc:
        return {"error": f"Failed to fetch URL: {exc}"}

    html_content = fetched.html
    final_url = fetched.final_url
    page_soup = BeautifulSoup(html_content, "html.parser")
    title = page_soup.title.get_text(strip=True) if page_soup.title else ""

    readability_success = False
    try:
        doc = Document(html_content)
        title = doc.title() or title
        cleaned_html = doc.summary()
        cleaned_text = BeautifulSoup(cleaned_html, "html.parser").get_text(" ", strip=True)
        readability_success = len(cleaned_text) >= 200
        if not readability_success:
            cleaned_html = _fallback_content(page_soup)
    except Exception:
        cleaned_html = _fallback_content(page_soup)

    cleaned_html = _clean_fragment(cleaned_html, final_url)

    try:
        markdown_text = md(
            cleaned_html,
            heading_style="ATX",
            bullets="-",
            default_title=False,
        )
    except Exception as exc:
        return {"error": f"Failed to parse content: {exc}"}

    markdown_text = _normalize_markdown(markdown_text, title)
    return {
        "title": title,
        "markdown": markdown_text,
        "character_count": len(markdown_text),
        "readability_success": readability_success,
    }
