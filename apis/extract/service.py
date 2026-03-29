import re
import json
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
    """Extract article content using readability algorithm with confidence scoring."""
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
    date = _extract_meta(
        full_soup, ["article:published_time", "date", "pubdate", "dc.date"]
    )

    # Language detection from html tag or meta
    language = ""
    html_tag = full_soup.find("html")
    if html_tag:
        language = html_tag.get("lang", "")
    if not language:
        language = _extract_meta(full_soup, ["language", "content-language"])

    # Confidence scoring
    confidence = _article_confidence(doc.title(), body, author, date, images)

    return {
        "title": doc.title(),
        "author": author,
        "date": date,
        "body": body,
        "images": images[:20],
        "word_count": len(body.split()),
        "language": language,
        "source_url": final_url,
        "confidence": confidence,
    }


def _article_confidence(
    title: str, body: str, author: str, date: str, images: list
) -> dict:
    """Score extraction confidence per field and overall."""
    scores = {}

    # Title
    if title and len(title) > 5 and len(title) < 300:
        scores["title"] = 1.0
    elif title:
        scores["title"] = 0.5
    else:
        scores["title"] = 0.0

    # Body
    word_count = len(body.split())
    if word_count > 200:
        scores["body"] = 1.0
    elif word_count > 50:
        scores["body"] = 0.7
    elif word_count > 10:
        scores["body"] = 0.3
    else:
        scores["body"] = 0.0

    # Author
    scores["author"] = 1.0 if author else 0.0

    # Date
    scores["date"] = 1.0 if date else 0.0

    # Images
    if len(images) >= 3:
        scores["images"] = 1.0
    elif len(images) >= 1:
        scores["images"] = 0.7
    else:
        scores["images"] = 0.0

    scores["overall"] = round(sum(scores.values()) / len(scores), 2)

    return scores


# ─── Contact Extraction ─────────────────────────────────────────


async def extract_contact(url: str) -> dict:
    """Extract emails, phones, addresses, and social links with confidence."""
    html, final_url = await _fetch_page(url)
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ", strip=True)

    # Emails
    email_pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    emails = list(set(re.findall(email_pattern, text)))
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("mailto:"):
            email = a["href"].replace("mailto:", "").split("?")[0]
            if email not in emails:
                emails.append(email)

    # Phones
    phone_pattern = r"[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{7,15}"
    phones = list(set(re.findall(phone_pattern, text)))
    phones = [p.strip() for p in phones if 7 <= len(re.sub(r"\D", "", p)) <= 15]

    # Social links
    social_domains = {
        "twitter.com": "twitter",
        "x.com": "twitter",
        "linkedin.com": "linkedin",
        "facebook.com": "facebook",
        "instagram.com": "instagram",
        "github.com": "github",
        "youtube.com": "youtube",
        "tiktok.com": "tiktok",
        "pinterest.com": "pinterest",
        "reddit.com": "reddit",
        "mastodon.social": "mastodon",
        "threads.net": "threads",
    }
    social_links = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        for domain, platform in social_domains.items():
            if domain in href and platform not in social_links:
                social_links[platform] = a["href"]

    # Addresses
    addresses = []
    address_patterns = [
        r"\d{1,5}\s[\w\s]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Road|Rd|Lane|Ln|Way|Court|Ct)[\w\s,]*\d{5}",
    ]
    for pattern in address_patterns:
        found = re.findall(pattern, text, re.IGNORECASE)
        addresses.extend(found)

    # Confidence
    confidence = _contact_confidence(emails, phones, social_links, addresses)

    return {
        "emails": emails[:10],
        "phones": phones[:10],
        "addresses": addresses[:5],
        "social_links": social_links,
        "source_url": final_url,
        "confidence": confidence,
    }


def _contact_confidence(
    emails: list, phones: list, social_links: dict, addresses: list
) -> dict:
    scores = {}
    scores["emails"] = min(1.0, len(emails) * 0.5) if emails else 0.0
    scores["phones"] = min(1.0, len(phones) * 0.5) if phones else 0.0
    scores["social_links"] = min(1.0, len(social_links) * 0.25) if social_links else 0.0
    scores["addresses"] = 1.0 if addresses else 0.0

    found = sum(1 for v in scores.values() if v > 0)
    scores["overall"] = round(found / len(scores), 2)

    return scores


# ─── Product Extraction ─────────────────────────────────────────


async def extract_product(url: str) -> dict:
    """Extract product data using structured data with enhanced fields and confidence."""
    html, final_url = await _fetch_page(url)
    soup = BeautifulSoup(html, "lxml")

    result = {
        "name": "",
        "price": "",
        "currency": "",
        "description": "",
        "images": [],
        "sku": "",
        "brand": "",
        "availability": "",
        "rating": None,
        "review_count": None,
        "source_url": final_url,
        "extraction_method": "none",
    }

    # 1. Try JSON-LD structured data first (most reliable)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            # Handle @graph wrapper
            if isinstance(data, dict) and "@graph" in data:
                data = data["@graph"]
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and (
                        item.get("@type") == "Product"
                        or "Product" in str(item.get("@type", ""))
                    ):
                        data = item
                        break
                else:
                    if data:
                        data = data[0]

            if isinstance(data, dict) and (
                data.get("@type") == "Product"
                or "Product" in str(data.get("@type", ""))
            ):
                result["name"] = data.get("name", "")
                result["description"] = data.get("description", "")
                result["sku"] = data.get("sku", "")
                result["brand"] = _extract_brand(data)
                result["extraction_method"] = "json-ld"

                # Price from offers
                offers = data.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0]
                if isinstance(offers, dict):
                    result["price"] = str(offers.get("price", ""))
                    result["currency"] = offers.get("priceCurrency", "")
                    avail = offers.get("availability", "")
                    result["availability"] = avail.split("/")[-1] if avail else ""

                # Rating
                agg_rating = data.get("aggregateRating", {})
                if isinstance(agg_rating, dict):
                    try:
                        result["rating"] = float(agg_rating.get("ratingValue", 0))
                    except (ValueError, TypeError):
                        pass
                    try:
                        result["review_count"] = int(
                            agg_rating.get("reviewCount", 0)
                            or agg_rating.get("ratingCount", 0)
                        )
                    except (ValueError, TypeError):
                        pass

                # Images
                img = data.get("image", [])
                if isinstance(img, str):
                    result["images"] = [img]
                elif isinstance(img, dict):
                    result["images"] = [img.get("url", "")]
                elif isinstance(img, list):
                    result["images"] = [
                        i if isinstance(i, str) else i.get("url", "")
                        for i in img[:10]
                    ]

                result["confidence"] = _product_confidence(result)
                return result
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    # 2. Try microdata (itemprop attributes)
    price_elem = soup.find(attrs={"itemprop": "price"})
    if price_elem:
        price_val = price_elem.get("content") or price_elem.get_text(strip=True)
        if price_val:
            result["price"] = price_val
            result["extraction_method"] = "microdata"
        currency_elem = soup.find(attrs={"itemprop": "priceCurrency"})
        if currency_elem:
            result["currency"] = (
                currency_elem.get("content") or currency_elem.get_text(strip=True)
            )

    name_elem = soup.find(attrs={"itemprop": "name"})
    if name_elem and not result["name"]:
        result["name"] = name_elem.get_text(strip=True)
        if not result["extraction_method"]:
            result["extraction_method"] = "microdata"

    brand_elem = soup.find(attrs={"itemprop": "brand"})
    if brand_elem:
        result["brand"] = brand_elem.get_text(strip=True)

    rating_elem = soup.find(attrs={"itemprop": "ratingValue"})
    if rating_elem:
        try:
            result["rating"] = float(
                rating_elem.get("content") or rating_elem.get_text(strip=True)
            )
        except (ValueError, TypeError):
            pass

    review_elem = soup.find(attrs={"itemprop": "reviewCount"})
    if review_elem:
        try:
            result["review_count"] = int(
                review_elem.get("content") or review_elem.get_text(strip=True)
            )
        except (ValueError, TypeError):
            pass

    # 3. Fallback: meta tags + heuristics
    if not result["name"]:
        result["name"] = _extract_meta(soup, ["og:title", "twitter:title"]) or (
            soup.title.string if soup.title else ""
        )
        if result["name"] and not result["extraction_method"]:
            result["extraction_method"] = "heuristic"

    if not result["description"]:
        result["description"] = _extract_meta(soup, ["og:description", "description"])

    og_image = _extract_meta(soup, ["og:image"])
    if og_image and not result["images"]:
        result["images"] = [og_image]

    # Price fallback
    if not result["price"]:
        text = soup.get_text()
        price_patterns = [
            r"[\$€£¥]\s*\d{1,6}[.,]\d{2}",
            r"\d{1,6}[.,]\d{2}\s*(?:USD|EUR|GBP|CAD|AUD)",
        ]
        all_prices = []
        for pattern in price_patterns:
            all_prices.extend(re.findall(pattern, text))

        if all_prices:

            def _parse_amount(p: str) -> float:
                cleaned = re.sub(r"[^\d.,]", "", p).replace(",", "")
                try:
                    return float(cleaned)
                except ValueError:
                    return 0.0

            priced = [(p, _parse_amount(p)) for p in all_prices]
            reasonable = [(p, v) for p, v in priced if v >= 5.0]
            if reasonable:
                result["price"] = reasonable[0][0].strip()
            elif all_prices:
                result["price"] = all_prices[0].strip()

            if not result["extraction_method"]:
                result["extraction_method"] = "heuristic"

    result["confidence"] = _product_confidence(result)
    return result


def _extract_brand(data: dict) -> str:
    """Extract brand from JSON-LD data."""
    brand = data.get("brand", "")
    if isinstance(brand, dict):
        return brand.get("name", "")
    if isinstance(brand, str):
        return brand
    return ""


def _product_confidence(result: dict) -> dict:
    scores = {}

    # Name
    if result["name"] and len(result["name"]) > 2:
        scores["name"] = 1.0
    elif result["name"]:
        scores["name"] = 0.5
    else:
        scores["name"] = 0.0

    # Price
    if result["price"] and result["currency"]:
        scores["price"] = 1.0
    elif result["price"]:
        scores["price"] = 0.7
    else:
        scores["price"] = 0.0

    # Description
    if result["description"] and len(result["description"]) > 20:
        scores["description"] = 1.0
    elif result["description"]:
        scores["description"] = 0.5
    else:
        scores["description"] = 0.0

    # Images
    if len(result["images"]) >= 2:
        scores["images"] = 1.0
    elif len(result["images"]) == 1:
        scores["images"] = 0.7
    else:
        scores["images"] = 0.0

    # Method bonus
    method = result.get("extraction_method", "")
    if method == "json-ld":
        method_bonus = 0.2
    elif method == "microdata":
        method_bonus = 0.1
    else:
        method_bonus = 0.0

    raw_overall = sum(scores.values()) / len(scores)
    scores["overall"] = round(min(1.0, raw_overall + method_bonus), 2)

    return scores


# ─── Recipe Extraction ───────────────────────────────────────────


async def extract_recipe(url: str) -> dict:
    """Extract recipe data from schema.org Recipe structured data."""
    html, final_url = await _fetch_page(url)
    soup = BeautifulSoup(html, "lxml")

    result = {
        "name": "",
        "description": "",
        "author": "",
        "prep_time": "",
        "cook_time": "",
        "total_time": "",
        "servings": "",
        "ingredients": [],
        "instructions": [],
        "images": [],
        "cuisine": "",
        "category": "",
        "calories": "",
        "rating": None,
        "review_count": None,
        "source_url": final_url,
        "extraction_method": "none",
    }

    # 1. JSON-LD (primary)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and "@graph" in data:
                data = data["@graph"]
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and (
                        item.get("@type") == "Recipe"
                        or "Recipe" in str(item.get("@type", ""))
                    ):
                        data = item
                        break
                else:
                    continue

            if not isinstance(data, dict):
                continue
            if data.get("@type") != "Recipe" and "Recipe" not in str(
                data.get("@type", "")
            ):
                continue

            result["name"] = data.get("name", "")
            result["description"] = data.get("description", "")
            result["extraction_method"] = "json-ld"

            # Author
            author = data.get("author", "")
            if isinstance(author, dict):
                result["author"] = author.get("name", "")
            elif isinstance(author, list) and author:
                a = author[0]
                result["author"] = a.get("name", "") if isinstance(a, dict) else str(a)
            elif isinstance(author, str):
                result["author"] = author

            # Times (ISO 8601 durations like PT30M)
            result["prep_time"] = _parse_duration(data.get("prepTime", ""))
            result["cook_time"] = _parse_duration(data.get("cookTime", ""))
            result["total_time"] = _parse_duration(data.get("totalTime", ""))

            # Servings
            yield_val = data.get("recipeYield", "")
            if isinstance(yield_val, list):
                yield_val = yield_val[0] if yield_val else ""
            result["servings"] = str(yield_val)

            # Ingredients
            ingredients = data.get("recipeIngredient", [])
            if isinstance(ingredients, list):
                result["ingredients"] = [str(i).strip() for i in ingredients]

            # Instructions
            instructions = data.get("recipeInstructions", [])
            result["instructions"] = _parse_instructions(instructions)

            # Images
            img = data.get("image", [])
            if isinstance(img, str):
                result["images"] = [img]
            elif isinstance(img, dict):
                result["images"] = [img.get("url", "")]
            elif isinstance(img, list):
                result["images"] = [
                    i if isinstance(i, str) else i.get("url", "")
                    for i in img[:10]
                ]

            # Category / cuisine
            result["cuisine"] = (
                data.get("recipeCuisine", "")
                if isinstance(data.get("recipeCuisine"), str)
                else ", ".join(data.get("recipeCuisine", []))
            )
            result["category"] = (
                data.get("recipeCategory", "")
                if isinstance(data.get("recipeCategory"), str)
                else ", ".join(data.get("recipeCategory", []))
            )

            # Nutrition
            nutrition = data.get("nutrition", {})
            if isinstance(nutrition, dict):
                result["calories"] = nutrition.get("calories", "")

            # Rating
            agg_rating = data.get("aggregateRating", {})
            if isinstance(agg_rating, dict):
                try:
                    result["rating"] = float(agg_rating.get("ratingValue", 0))
                except (ValueError, TypeError):
                    pass
                try:
                    result["review_count"] = int(
                        agg_rating.get("reviewCount", 0)
                        or agg_rating.get("ratingCount", 0)
                    )
                except (ValueError, TypeError):
                    pass

            result["confidence"] = _recipe_confidence(result)
            return result
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    # 2. Fallback: meta tags
    result["name"] = _extract_meta(soup, ["og:title", "twitter:title"]) or (
        soup.title.string if soup.title else ""
    )
    result["description"] = _extract_meta(soup, ["og:description", "description"])
    og_image = _extract_meta(soup, ["og:image"])
    if og_image:
        result["images"] = [og_image]
    result["extraction_method"] = "heuristic"
    result["confidence"] = _recipe_confidence(result)

    return result


def _parse_duration(iso: str) -> str:
    """Convert ISO 8601 duration (PT1H30M) to human readable string."""
    if not iso:
        return ""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not match:
        return iso
    hours, minutes, seconds = match.groups()
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds:
        parts.append(f"{seconds}s")
    return " ".join(parts) if parts else iso


def _parse_instructions(instructions) -> list[str]:
    """Parse recipe instructions from various JSON-LD formats."""
    if isinstance(instructions, str):
        return [instructions]
    if not isinstance(instructions, list):
        return []

    result = []
    for item in instructions:
        if isinstance(item, str):
            result.append(item.strip())
        elif isinstance(item, dict):
            if item.get("@type") == "HowToStep":
                result.append(item.get("text", "").strip())
            elif item.get("@type") == "HowToSection":
                section_name = item.get("name", "")
                if section_name:
                    result.append(f"## {section_name}")
                sub_items = item.get("itemListElement", [])
                result.extend(_parse_instructions(sub_items))
    return result


def _recipe_confidence(result: dict) -> dict:
    scores = {}

    scores["name"] = 1.0 if result["name"] else 0.0
    scores["ingredients"] = (
        1.0
        if len(result["ingredients"]) >= 3
        else 0.5 if result["ingredients"] else 0.0
    )
    scores["instructions"] = (
        1.0
        if len(result["instructions"]) >= 2
        else 0.5 if result["instructions"] else 0.0
    )
    scores["times"] = (
        1.0 if result["total_time"] or (result["prep_time"] and result["cook_time"])
        else 0.5 if result["prep_time"] or result["cook_time"]
        else 0.0
    )
    scores["images"] = 1.0 if result["images"] else 0.0

    scores["overall"] = round(sum(scores.values()) / len(scores), 2)
    return scores


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
