import re
import logging
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("api.extract")

# Shared HTTP client
_client = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=False,  # Windows SSL cert store compatibility
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            },
        )
    return _client


async def _fetch_page(url: str) -> tuple[str, str]:
    """Fetch a URL and return (html_content, final_url)."""
    client = _get_client()
    response = await client.get(url)
    response.raise_for_status()
    return response.text, str(response.url)


# ─── Article Extraction ─────────────────────────────────────────


async def extract_article(url: str) -> dict:
    """Extract article content using readability algorithm."""
    from readability import Document

    html, final_url = await _fetch_page(url)

    doc = Document(html)
    soup = BeautifulSoup(doc.summary(), "lxml")

    # Extract body text
    body = soup.get_text(separator="\n", strip=True)

    # Extract images
    images = []
    for img in soup.find_all("img", src=True):
        src = urljoin(final_url, img["src"])
        if src not in images:
            images.append(src)

    # Try to find author & date from the original HTML
    full_soup = BeautifulSoup(html, "lxml")
    author = _extract_meta(full_soup, ["author", "article:author", "og:article:author"])
    date = _extract_meta(full_soup, ["article:published_time", "date", "pubdate", "dc.date"])

    return {
        "title": doc.title(),
        "author": author,
        "date": date,
        "body": body,
        "images": images[:20],  # Cap at 20
        "word_count": len(body.split()),
        "source_url": final_url,
    }


# ─── Contact Extraction ─────────────────────────────────────────


async def extract_contact(url: str) -> dict:
    """Extract emails, phones, addresses, and social links from a page."""
    html, final_url = await _fetch_page(url)
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ", strip=True)

    # Emails
    email_pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    emails = list(set(re.findall(email_pattern, text)))
    # Also check mailto: links
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("mailto:"):
            email = a["href"].replace("mailto:", "").split("?")[0]
            if email not in emails:
                emails.append(email)

    # Phones
    phone_pattern = r"[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{7,15}"
    phones = list(set(re.findall(phone_pattern, text)))
    # Filter out likely false positives (too many digits or too few)
    phones = [p.strip() for p in phones if 7 <= len(re.sub(r"\D", "", p)) <= 15]

    # Social links
    social_domains = {
        "twitter.com": "twitter", "x.com": "twitter",
        "linkedin.com": "linkedin",
        "facebook.com": "facebook",
        "instagram.com": "instagram",
        "github.com": "github",
        "youtube.com": "youtube",
        "tiktok.com": "tiktok",
    }
    social_links = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        for domain, platform in social_domains.items():
            if domain in href and platform not in social_links:
                social_links[platform] = a["href"]

    # Addresses (simple heuristic: look for common patterns)
    addresses = []
    address_patterns = [
        r"\d{1,5}\s[\w\s]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Road|Rd|Lane|Ln|Way|Court|Ct)[\w\s,]*\d{5}",
    ]
    for pattern in address_patterns:
        found = re.findall(pattern, text, re.IGNORECASE)
        addresses.extend(found)

    return {
        "emails": emails[:10],
        "phones": phones[:10],
        "addresses": addresses[:5],
        "social_links": social_links,
        "source_url": final_url,
    }


# ─── Product Extraction ─────────────────────────────────────────


async def extract_product(url: str) -> dict:
    """Extract product data from a product page using structured data and heuristics."""
    html, final_url = await _fetch_page(url)
    soup = BeautifulSoup(html, "lxml")

    result = {
        "name": "",
        "price": "",
        "currency": "",
        "description": "",
        "images": [],
        "sku": "",
        "availability": "",
        "source_url": final_url,
    }

    # 1. Try JSON-LD structured data first (most reliable)
    import json
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0]
            if data.get("@type") == "Product" or "Product" in str(data.get("@type", "")):
                result["name"] = data.get("name", "")
                result["description"] = data.get("description", "")
                result["sku"] = data.get("sku", "")

                # Price from offers
                offers = data.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0]
                if isinstance(offers, dict):
                    result["price"] = str(offers.get("price", ""))
                    result["currency"] = offers.get("priceCurrency", "")
                    result["availability"] = offers.get("availability", "").split("/")[-1]

                # Images
                img = data.get("image", [])
                if isinstance(img, str):
                    result["images"] = [img]
                elif isinstance(img, list):
                    result["images"] = img[:10]

                return result
        except (json.JSONDecodeError, TypeError):
            continue

    # 2. Try microdata (itemprop attributes)
    price_elem = soup.find(attrs={"itemprop": "price"})
    if price_elem:
        price_val = price_elem.get("content") or price_elem.get_text(strip=True)
        if price_val:
            result["price"] = price_val
        currency_elem = soup.find(attrs={"itemprop": "priceCurrency"})
        if currency_elem:
            result["currency"] = currency_elem.get("content") or currency_elem.get_text(strip=True)

    name_elem = soup.find(attrs={"itemprop": "name"})
    if name_elem and not result["name"]:
        result["name"] = name_elem.get_text(strip=True)

    # 3. Fallback: meta tags + heuristics
    if not result["name"]:
        result["name"] = _extract_meta(soup, ["og:title", "twitter:title"]) or (soup.title.string if soup.title else "")
    if not result["description"]:
        result["description"] = _extract_meta(soup, ["og:description", "description"])

    og_image = _extract_meta(soup, ["og:image"])
    if og_image and not result["images"]:
        result["images"] = [og_image]

    # Price fallback: find all prices and pick the most likely product price
    if not result["price"]:
        text = soup.get_text()
        price_patterns = [
            r"[\$€£¥]\s*\d{1,6}[.,]\d{2}",  # $99.99 or €1,299.99
            r"\d{1,6}[.,]\d{2}\s*(?:USD|EUR|GBP|CAD|AUD)",  # 99.99 USD
        ]
        all_prices = []
        for pattern in price_patterns:
            all_prices.extend(re.findall(pattern, text))

        if all_prices:
            # Pick the price that looks most like a product price (not the cheapest)
            # Products are typically $5+ ; filter out tiny ancillary prices
            def _parse_amount(p: str) -> float:
                cleaned = re.sub(r"[^\d.,]", "", p).replace(",", "")
                try:
                    return float(cleaned)
                except ValueError:
                    return 0.0

            # Sort by value, pick median or first reasonable price
            priced = [(p, _parse_amount(p)) for p in all_prices]
            reasonable = [(p, v) for p, v in priced if v >= 5.0]
            if reasonable:
                result["price"] = reasonable[0][0].strip()
            elif all_prices:
                result["price"] = all_prices[0].strip()

    return result


# ─── Helpers ─────────────────────────────────────────────────────


def _extract_meta(soup: BeautifulSoup, names: list[str]) -> str:
    """Try to extract content from meta tags by name or property."""
    for name in names:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"]
        tag = soup.find("meta", attrs={"property": name})
        if tag and tag.get("content"):
            return tag["content"]
    return ""
