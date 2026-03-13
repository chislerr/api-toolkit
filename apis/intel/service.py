import re
import time
import logging
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("api.intel")

_client = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=False,  # Windows SSL cert store compatibility
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )
    return _client


async def audit_site(url: str) -> dict:
    """Run a full site intelligence audit: meta tags, tech stack, security, performance, broken links."""
    client = _get_client()

    start_time = time.perf_counter()
    response = await client.get(url)
    load_time_ms = int((time.perf_counter() - start_time) * 1000)

    response.raise_for_status()
    html = response.text
    final_url = str(response.url)
    headers = dict(response.headers)
    soup = BeautifulSoup(html, "lxml")

    result = {
        "url": final_url,
        "meta_tags": _extract_meta_tags(soup),
        "tech_stack": _detect_tech_stack(soup, html, headers),
        "security_headers": _check_security_headers(headers),
        "performance": {
            "page_size_bytes": len(html.encode()),
            "page_size_readable": _format_bytes(len(html.encode())),
            "load_time_ms": load_time_ms,
            "num_requests": 1,  # We only count the main request from server side
        },
        "broken_links": await _check_broken_links(soup, final_url, client),
        "is_mobile_friendly": _check_mobile_friendly(soup),
        "source_url": final_url,
    }

    return result


# ─── Meta Tags ───────────────────────────────────────────────────


def _extract_meta_tags(soup: BeautifulSoup) -> dict:
    def meta(names):
        for n in names:
            tag = soup.find("meta", attrs={"name": n}) or soup.find("meta", attrs={"property": n})
            if tag and tag.get("content"):
                return tag["content"]
        return ""

    canonical = ""
    link = soup.find("link", rel="canonical")
    if link and link.get("href"):
        canonical = link["href"]

    return {
        "title": soup.title.string.strip() if soup.title and soup.title.string else "",
        "description": meta(["description", "og:description"]),
        "canonical": canonical,
        "og_title": meta(["og:title"]),
        "og_description": meta(["og:description"]),
        "og_image": meta(["og:image"]),
        "twitter_card": meta(["twitter:card"]),
    }


# ─── Tech Stack Detection ───────────────────────────────────────


def _detect_tech_stack(soup: BeautifulSoup, html: str, headers: dict) -> list[str]:
    """Detect technologies by analyzing scripts, meta tags, headers, and HTML patterns."""
    detected = set()

    # Header-based detection
    server = headers.get("server", "").lower()
    powered_by = headers.get("x-powered-by", "").lower()

    header_map = {
        "nginx": "Nginx", "apache": "Apache", "cloudflare": "Cloudflare",
        "iis": "IIS", "litespeed": "LiteSpeed", "vercel": "Vercel",
        "netlify": "Netlify",
    }
    for key, name in header_map.items():
        if key in server or key in powered_by:
            detected.add(name)

    if "x-vercel" in headers or "x-vercel-id" in headers:
        detected.add("Vercel")

    # Script-based detection
    script_patterns = {
        "react": "React", "vue": "Vue.js", "angular": "Angular",
        "jquery": "jQuery", "bootstrap": "Bootstrap", "tailwind": "Tailwind CSS",
        "next": "Next.js", "nuxt": "Nuxt.js", "gatsby": "Gatsby",
        "svelte": "Svelte", "alpine": "Alpine.js", "htmx": "HTMX",
        "google-analytics": "Google Analytics", "analytics.js": "Google Analytics",
        "gtag": "Google Tag Manager", "gtm.js": "Google Tag Manager",
        "facebook.net": "Facebook Pixel", "hotjar": "Hotjar",
        "stripe": "Stripe", "shopify": "Shopify", "woocommerce": "WooCommerce",
        "wp-content": "WordPress", "wp-includes": "WordPress",
    }

    for script in soup.find_all("script", src=True):
        src = script["src"].lower()
        for pattern, tech in script_patterns.items():
            if pattern in src:
                detected.add(tech)

    # HTML pattern detection
    html_lower = html.lower()
    html_patterns = {
        "__next": "Next.js",
        "__nuxt": "Nuxt.js",
        "data-reactroot": "React",
        "ng-app": "Angular",
        "v-cloak": "Vue.js",
        "data-svelte": "Svelte",
        "shopify": "Shopify",
    }
    for pattern, tech in html_patterns.items():
        if pattern in html_lower:
            detected.add(tech)

    # Meta generator tag
    generator = soup.find("meta", attrs={"name": "generator"})
    if generator and generator.get("content"):
        detected.add(generator["content"].split()[0])

    return sorted(detected)


# ─── Security Headers ────────────────────────────────────────────


def _check_security_headers(headers: dict) -> dict:
    checks = {
        "strict-transport-security": ("has_hsts", "HSTS"),
        "content-security-policy": ("has_csp", "Content-Security-Policy"),
        "x-frame-options": ("has_x_frame_options", "X-Frame-Options"),
        "x-content-type-options": ("has_x_content_type", "X-Content-Type-Options"),
        "referrer-policy": ("has_referrer_policy", "Referrer-Policy"),
    }

    result = {"details": {}}
    score_count = 0

    for header_name, (field, display_name) in checks.items():
        value = headers.get(header_name, "")
        present = bool(value)
        result[field] = present
        if present:
            result["details"][display_name] = value
            score_count += 1

    # Grade: A=5, B=4, C=3, D=2, F=0-1
    grades = {5: "A", 4: "B", 3: "C", 2: "D"}
    result["score"] = grades.get(score_count, "F")

    return result


# ─── Broken Link Check ───────────────────────────────────────────


async def _check_broken_links(soup: BeautifulSoup, base_url: str, client: httpx.AsyncClient) -> list[str]:
    """Check internal links on the page for 4xx/5xx errors. Parallelized, limited to 10 links."""
    import asyncio

    checked = set()
    base_domain = urlparse(base_url).netloc
    urls_to_check = []

    for a in soup.find_all("a", href=True):
        if len(urls_to_check) >= 10:
            break

        href = a["href"]
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        if parsed.netloc != base_domain:
            continue
        if full_url in checked:
            continue

        checked.add(full_url)
        urls_to_check.append(full_url)

    async def _check_one(url: str) -> str | None:
        try:
            resp = await client.head(url, timeout=5.0)
            return url if resp.status_code >= 400 else None
        except Exception:
            return url

    results = await asyncio.gather(*[_check_one(u) for u in urls_to_check])
    return [url for url in results if url is not None]


# ─── Mobile Friendly Check ───────────────────────────────────────


def _check_mobile_friendly(soup: BeautifulSoup) -> bool:
    """Basic check for viewport meta tag (primary mobile-friendliness signal)."""
    viewport = soup.find("meta", attrs={"name": "viewport"})
    return viewport is not None and "width" in (viewport.get("content", "").lower())


# ─── Helpers ─────────────────────────────────────────────────────


def _format_bytes(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
