import time
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from core.ssrf import validate_url

# ─── HTTP Client ──────────────────────────────────────────────────


def _get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    )


# ─── Helpers ──────────────────────────────────────────────────────


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _check_security_headers(headers: dict) -> dict:
    headers_lower = {k.lower(): v for k, v in headers.items()}

    checks = {
        "strict-transport-security": "has_hsts",
        "content-security-policy": "has_csp",
        "x-frame-options": "has_x_frame_options",
        "x-content-type-options": "has_x_content_type",
        "referrer-policy": "has_referrer_policy",
    }

    results = {}
    score = 0
    details = {}

    for header, field in checks.items():
        present = header in headers_lower
        results[field] = present
        details[header] = "Present" if present else "Missing"
        if present:
            score += 1

    if score == 5:
        grade = "A"
    elif score >= 4:
        grade = "B"
    elif score >= 3:
        grade = "C"
    elif score >= 2:
        grade = "D"
    else:
        grade = "F"

    results["score"] = grade
    results["details"] = details
    return results


def _detect_tech_stack(soup: BeautifulSoup, headers: dict, html: str) -> list:
    technologies = []

    headers_lower = {k.lower(): v for k, v in headers.items()}

    server = headers_lower.get("server", "")
    if "nginx" in server.lower():
        technologies.append("Nginx")
    if "apache" in server.lower():
        technologies.append("Apache")
    if "cloudflare" in server.lower():
        technologies.append("Cloudflare")
    if "google" in server.lower():
        technologies.append("Google Cloud")

    powered_by = headers_lower.get("x-powered-by", "")
    if "express" in powered_by.lower():
        technologies.append("Express.js")
    if "next.js" in powered_by.lower():
        technologies.append("Next.js")
    if "php" in powered_by.lower():
        technologies.append("PHP")
    if "asp.net" in powered_by.lower():
        technologies.append("ASP.NET")

    if soup.find("script", src=lambda x: x and "react" in x.lower()):
        technologies.append("React")
    if soup.find("script", src=lambda x: x and "angular" in x.lower()):
        technologies.append("Angular")
    if soup.find("script", src=lambda x: x and "vue" in x.lower()):
        technologies.append("Vue.js")
    if soup.find("script", src=lambda x: x and "jquery" in x.lower()):
        technologies.append("jQuery")
    if soup.find("script", src=lambda x: x and "bootstrap" in x.lower()):
        technologies.append("Bootstrap")
    if soup.find("script", src=lambda x: x and "tailwind" in x.lower()):
        technologies.append("Tailwind CSS")
    if soup.find("link", href=lambda x: x and "tailwind" in x.lower()):
        if "Tailwind CSS" not in technologies:
            technologies.append("Tailwind CSS")

    if soup.find("meta", attrs={"name": "generator"}):
        generator = soup.find("meta", attrs={"name": "generator"}).get("content", "")
        if "wordpress" in generator.lower():
            technologies.append("WordPress")
        if "drupal" in generator.lower():
            technologies.append("Drupal")
        if "joomla" in generator.lower():
            technologies.append("Joomla")
        if "wix" in generator.lower():
            technologies.append("Wix")
        if "squarespace" in generator.lower():
            technologies.append("Squarespace")
        if "shopify" in generator.lower():
            technologies.append("Shopify")
        if "webflow" in generator.lower():
            technologies.append("Webflow")

    if soup.find("script", src=lambda x: x and "googletagmanager" in x.lower()):
        technologies.append("Google Tag Manager")
    if soup.find("script", src=lambda x: x and "google-analytics" in x.lower()):
        technologies.append("Google Analytics")
    if soup.find("script", src=lambda x: x and "facebook" in x.lower()):
        technologies.append("Facebook Pixel")
    if soup.find("script", src=lambda x: x and "hotjar" in x.lower()):
        technologies.append("Hotjar")

    if soup.find("link", href=lambda x: x and "fonts.googleapis" in x.lower()):
        technologies.append("Google Fonts")

    if "x-shopid" in headers_lower:
        technologies.append("Shopify")
    if "x-wix-request-id" in headers_lower:
        technologies.append("Wix")
    if "x-vercel-id" in headers_lower:
        technologies.append("Vercel")
    if "x-render-origin-server" in headers_lower:
        technologies.append("Render")
    if "x-amz-cf-id" in headers_lower or "x-amz-request-id" in headers_lower:
        technologies.append("AWS CloudFront")
    if "x-fastly" in headers_lower or "x-served-by" in headers_lower:
        technologies.append("Fastly")
    if "cf-ray" in headers_lower:
        if "Cloudflare" not in technologies:
            technologies.append("Cloudflare")
    if "x-github-request-id" in headers_lower:
        technologies.append("GitHub Pages")
    if "x-netlify" in headers_lower:
        technologies.append("Netlify")

    return technologies


# ─── Main Audit Function ──────────────────────────────────────────


async def full_audit(url: str) -> dict:
    """Perform a comprehensive website audit."""
    validate_url(url)

    start_time = time.time()
    async with _get_client() as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
        headers = dict(response.headers)
        load_time_ms = int((time.time() - start_time) * 1000)

    soup = BeautifulSoup(html, "html.parser")

    # Meta tags
    meta_tags = {}
    title_el = soup.find("title")
    meta_tags["title"] = title_el.get_text(strip=True) if title_el else ""

    for meta_name, prop_name in [
        ("description", "description"),
        ("og:title", "og:title"),
        ("og:description", "og:description"),
        ("og:image", "og:image"),
        ("twitter:card", "twitter:card"),
    ]:
        el = soup.find("meta", attrs={"name": meta_name}) or soup.find(
            "meta", attrs={"property": prop_name}
        )
        if el:
            key = meta_name.replace(":", "_")
            meta_tags[key] = el.get("content", "")

    canonical = soup.find("link", rel="canonical")
    if canonical:
        meta_tags["canonical"] = canonical.get("href", "")

    # Tech stack
    tech_stack = _detect_tech_stack(soup, headers, html)

    # Security headers
    security_headers = _check_security_headers(headers)

    # Performance
    page_size = len(html.encode("utf-8"))
    num_requests = 1
    for tag in soup.find_all(["script", "link", "img"]):
        if tag.get("src") or tag.get("href"):
            num_requests += 1

    # Broken links (internal only, check up to 20)
    broken_links = []
    parsed_base = urlparse(url)
    base_url = f"{parsed_base.scheme}://{parsed_base.netloc}"
    internal_links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        full_url = urljoin(url, href)
        if urlparse(full_url).netloc == parsed_base.netloc:
            internal_links.append(full_url)

    for link in internal_links[:20]:
        try:
            async with _get_client() as client:
                resp = await client.head(link, timeout=5.0)
                if resp.status_code >= 400:
                    broken_links.append(link)
        except Exception:
            pass

    # Mobile friendly (basic check)
    viewport = soup.find("meta", attrs={"name": "viewport"})
    is_mobile_friendly = viewport is not None

    return {
        "url": url,
        "meta_tags": meta_tags,
        "tech_stack": tech_stack,
        "security_headers": security_headers,
        "performance": {
            "page_size_bytes": page_size,
            "page_size_readable": _format_size(page_size),
            "load_time_ms": load_time_ms,
            "num_requests": num_requests,
        },
        "broken_links": broken_links,
        "is_mobile_friendly": is_mobile_friendly,
        "source_url": url,
    }
