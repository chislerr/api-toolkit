import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from core.fetch import build_async_client, fetch_html
from core.ssrf import validate_url


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
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
        details[header] = headers_lower.get(header, "Missing")
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


def _append_tech(technologies: list[str], name: str) -> None:
    if name not in technologies:
        technologies.append(name)


def _detect_tech_stack(soup: BeautifulSoup, headers: dict, html: str) -> list[str]:
    technologies: list[str] = []
    headers_lower = {k.lower(): v for k, v in headers.items()}
    html_lower = html.lower()

    server = headers_lower.get("server", "")
    if "nginx" in server.lower():
        _append_tech(technologies, "Nginx")
    if "apache" in server.lower():
        _append_tech(technologies, "Apache")
    if "cloudflare" in server.lower() or "cf-ray" in headers_lower:
        _append_tech(technologies, "Cloudflare")

    powered_by = headers_lower.get("x-powered-by", "")
    if "express" in powered_by.lower():
        _append_tech(technologies, "Express.js")
    if "next.js" in powered_by.lower() or "__next_data__" in html_lower or "/_next/" in html_lower:
        _append_tech(technologies, "Next.js")
    if "php" in powered_by.lower():
        _append_tech(technologies, "PHP")
    if "asp.net" in powered_by.lower():
        _append_tech(technologies, "ASP.NET")

    if "react" in html_lower or soup.find(attrs={"data-reactroot": True}):
        _append_tech(technologies, "React")
    if "ng-version" in html_lower:
        _append_tech(technologies, "Angular")
    if "/_nuxt/" in html_lower or 'id="__nuxt"' in html_lower:
        _append_tech(technologies, "Nuxt.js")
    if "vue" in html_lower:
        _append_tech(technologies, "Vue.js")
    if "jquery" in html_lower:
        _append_tech(technologies, "jQuery")
    if "bootstrap" in html_lower:
        _append_tech(technologies, "Bootstrap")
    if "tailwind" in html_lower:
        _append_tech(technologies, "Tailwind CSS")

    generator = soup.find("meta", attrs={"name": "generator"})
    generator_text = generator.get("content", "") if generator else ""
    if "wordpress" in generator_text.lower() or "wp-content" in html_lower or "wp-json" in html_lower:
        _append_tech(technologies, "WordPress")
    if "shopify" in generator_text.lower() or "cdn.shopify.com" in html_lower or "x-shopid" in headers_lower:
        _append_tech(technologies, "Shopify")
    if "wix" in generator_text.lower() or "wixstatic" in html_lower or "x-wix-request-id" in headers_lower:
        _append_tech(technologies, "Wix")
    if "webflow" in generator_text.lower() or "webflow" in html_lower:
        _append_tech(technologies, "Webflow")

    if "googletagmanager" in html_lower:
        _append_tech(technologies, "Google Tag Manager")
    if "google-analytics" in html_lower or "gtag/js" in html_lower:
        _append_tech(technologies, "Google Analytics")
    if "plausible" in html_lower:
        _append_tech(technologies, "Plausible Analytics")
    if "hotjar" in html_lower:
        _append_tech(technologies, "Hotjar")
    if "segment.com" in html_lower:
        _append_tech(technologies, "Segment")

    if "x-vercel-id" in headers_lower:
        _append_tech(technologies, "Vercel")
    if "x-render-origin-server" in headers_lower:
        _append_tech(technologies, "Render")
    if "x-amz-cf-id" in headers_lower or "x-amz-request-id" in headers_lower:
        _append_tech(technologies, "AWS CloudFront")
    if "x-fastly" in headers_lower or "x-served-by" in headers_lower:
        _append_tech(technologies, "Fastly")
    if "x-netlify" in headers_lower:
        _append_tech(technologies, "Netlify")

    return technologies


async def _find_broken_internal_links(url: str, soup: BeautifulSoup) -> list[str]:
    parsed_base = urlparse(url)
    candidates: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full_url = urljoin(url, href)
        if urlparse(full_url).netloc == parsed_base.netloc:
            candidates.append(full_url)

    unique_links = []
    for link in candidates:
        if link not in unique_links:
            unique_links.append(link)

    broken: list[str] = []
    async with build_async_client(timeout=10.0) as client:
        for link in unique_links[:20]:
            try:
                validate_url(link)
                response = await client.head(link)
                if response.status_code in {403, 405, 501}:
                    response = await client.get(link)
                if response.status_code >= 400:
                    broken.append(link)
            except Exception:
                broken.append(link)
    return broken


async def full_audit(url: str) -> dict:
    """Perform a comprehensive website audit."""
    validate_url(url)

    start_time = time.time()
    fetched = await fetch_html(url, timeout=20.0)
    load_time_ms = int((time.time() - start_time) * 1000)

    html = fetched.html
    headers = fetched.headers
    source_url = fetched.final_url
    soup = BeautifulSoup(html, "html.parser")

    meta_tags = {
        "title": soup.title.get_text(strip=True) if soup.title else "",
        "description": "",
        "og_title": "",
        "og_description": "",
        "og_image": "",
        "twitter_card": "",
        "canonical": "",
    }
    for key, names in {
        "description": ("description",),
        "og_title": ("og:title",),
        "og_description": ("og:description",),
        "og_image": ("og:image",),
        "twitter_card": ("twitter:card",),
    }.items():
        for name in names:
            tag = (
                soup.find("meta", attrs={"name": name})
                or soup.find("meta", attrs={"property": name})
            )
            if tag and tag.get("content"):
                meta_tags[key] = tag["content"]
                break

    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        meta_tags["canonical"] = urljoin(source_url, canonical["href"])

    tech_stack = _detect_tech_stack(soup, headers, html)
    security_headers = _check_security_headers(headers)
    page_size = len(html.encode("utf-8"))
    num_requests = 1 + len(
        [
            tag
            for tag in soup.find_all(["script", "link", "img"])
            if tag.get("src") or tag.get("href")
        ]
    )
    broken_links = await _find_broken_internal_links(source_url, soup)

    viewport = soup.find("meta", attrs={"name": "viewport"})
    is_mobile_friendly = bool(viewport and "width=device-width" in viewport.get("content", "").lower())

    return {
        "url": source_url,
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
        "source_url": source_url,
    }
