import re
import httpx
from readability import Document
from markdownify import markdownify as md
from core.ssrf import validate_url

async def extract_markdown_from_url(url: str) -> dict:
    """
    Fetches the HTML from a URL, extracts the main article content using readability,
    and converts it to clean markdown.
    """
    validate_url(url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html_content = response.text
    except Exception as e:
        return {"error": f"Failed to fetch URL: {str(e)}"}

    try:
        doc = Document(html_content)
        title = doc.title()
        cleaned_html = doc.summary()

        markdown_text = md(cleaned_html, heading_style="ATX", default_title=False).strip()
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)

        return {
            "title": title,
            "markdown": markdown_text,
            "character_count": len(markdown_text),
            "readability_success": True
        }
    except Exception as e:
        return {"error": f"Failed to parse content: {str(e)}"}
