import httpx
from readability import Document
from markdownify import markdownify as md

async def extract_markdown_from_url(url: str) -> dict:
    """
    Fetches the HTML from a URL, extracts the main article content using readability, 
    and converts it to clean markdown.
    """
    # Use a generic User-Agent to avoid simple bot blocks
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
        # 1. Parse with Readability to strip ads, navs, footers, etc.
        doc = Document(html_content)
        title = doc.title()
        cleaned_html = doc.summary() # This provides the 'clean' html of the main article body

        # 2. Convert to Markdown
        # strip=['a'] could remove links, but we probably want to keep them.
        # We'll use default markdownify settings which are generally quite good.
        markdown_text = md(cleaned_html, heading_style="ATX", default_title=False).strip()

        # Some minor cleanup in markdownify output (removing excessive blank lines)
        import re
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)

        return {
            "title": title,
            "markdown": markdown_text,
            "character_count": len(markdown_text),
            "readability_success": True
        }
    except Exception as e:
        return {"error": f"Failed to parse content: {str(e)}"}
