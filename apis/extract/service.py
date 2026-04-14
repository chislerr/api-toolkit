import json
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from readability import Document

from core.fetch import fetch_html
from core.ssrf import validate_url

logger = logging.getLogger("api-toolkit.extract")

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(
    r"(?:\+\d{1,3}[\s().-]*)?(?:\(?\d{2,4}\)?[\s().-]*){2,5}\d{2,4}"
)
PRICE_PATTERN = re.compile(
    r"(?P<prefix>USD|EUR|GBP|CAD|AUD|JPY|UAH|[$€£¥₴])?\s*"
    r"(?P<amount>\d[\d,.]*)"
    r"(?:\s*(?P<suffix>USD|EUR|GBP|CAD|AUD|JPY|UAH))?",
    re.IGNORECASE,
)
SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "twitter.com": "twitter",
    "x.com": "x",
    "linkedin.com": "linkedin",
    "instagram.com": "instagram",
    "youtube.com": "youtube",
    "tiktok.com": "tiktok",
    "github.com": "github",
}


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _coerce_text(value: object) -> str:
    if isinstance(value, dict):
        for key in ("name", "text", "value", "description", "url"):
            text = _coerce_text(value.get(key))
            if text:
                return text
        return ""
    if isinstance(value, list):
        for item in value:
            text = _coerce_text(item)
            if text:
                return text
        return ""
    return _clean_text(value)


def _dedupe(values: list[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if limit is not None and len(result) >= limit:
            break
    return result


def _normalize_url(value: object, base_url: str) -> str:
    text = _coerce_text(value)
    if not text:
        return ""
    return urljoin(base_url, text)


def _normalize_urls(value: object, base_url: str, limit: int = 10) -> list[str]:
    urls: list[str] = []

    def collect(item: object) -> None:
        if isinstance(item, dict):
            for key in ("url", "contentUrl", "src", "image"):
                if item.get(key):
                    collect(item[key])
                    return
            return
        if isinstance(item, list):
            for sub_item in item:
                collect(sub_item)
            return
        url = _normalize_url(item, base_url)
        if url:
            urls.append(url)

    collect(value)
    return _dedupe(urls, limit=limit)


def _extract_meta_content(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = (
            soup.find("meta", attrs={"property": name})
            or soup.find("meta", attrs={"name": name})
            or soup.find("meta", attrs={"itemprop": name})
        )
        if tag and tag.get("content"):
            return _clean_text(tag["content"])
    return ""


def _extract_from_selectors(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        element = soup.select_one(selector)
        if not element:
            continue
        value = (
            element.get("content")
            or element.get("value")
            or element.get("data-old-hires")
            or element.get("src")
            or element.get_text(" ", strip=True)
        )
        text = _clean_text(value)
        if text:
            return text
    return ""


def _extract_urls_from_selectors(
    soup: BeautifulSoup, selectors: list[str], base_url: str, limit: int = 10
) -> list[str]:
    urls: list[str] = []
    for selector in selectors:
        for element in soup.select(selector):
            candidate = (
                element.get("content")
                or element.get("data-old-hires")
                or element.get("src")
                or element.get("href")
                or element.get("data-src")
            )
            url = _normalize_url(candidate, base_url)
            if url:
                urls.append(url)
    return _dedupe(urls, limit=limit)


def _to_float(value: object) -> float | None:
    text = _coerce_text(value)
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _to_int(value: object) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _normalize_currency(value: str) -> str:
    mapping = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₴": "UAH"}
    token = _clean_text(value).upper()
    return mapping.get(token, token)


def _parse_price(price_value: object, currency_value: object = "") -> tuple[str, str]:
    price_text = _coerce_text(price_value).replace("\xa0", " ")
    currency = _normalize_currency(_coerce_text(currency_value)) if currency_value else ""
    if price_text:
        match = PRICE_PATTERN.search(price_text)
        if match:
            price = match.group("amount").replace(",", "")
            token = match.group("prefix") or match.group("suffix") or ""
            if not currency and token:
                currency = _normalize_currency(token)
            return price, currency
    if price_text and re.fullmatch(r"\d[\d,.]*", price_text):
        return price_text.replace(",", ""), currency
    return price_text, currency


def _strip_schema_value(value: object) -> str:
    text = _coerce_text(value)
    if text.startswith("http://") or text.startswith("https://"):
        return text.rstrip("/").rsplit("/", 1)[-1]
    return text


def _field_confidence(method: str, present: bool, bonus: float = 0.0) -> float:
    base = {"json-ld": 0.92, "microdata": 0.82, "dom": 0.64, "fallback": 0.45, "hybrid": 0.88}
    if not present:
        return 0.0
    return round(min(0.99, base.get(method, 0.5) + bonus), 2)


def _extract_json_ld_entities(soup: BeautifulSoup) -> list[dict]:
    entities: list[dict] = []

    def flatten(node: object) -> list[dict]:
        if isinstance(node, list):
            flat: list[dict] = []
            for item in node:
                flat.extend(flatten(item))
            return flat
        if not isinstance(node, dict):
            return []
        result = flatten(node.get("@graph", [])) if "@graph" in node else [node]
        main_entity = node.get("mainEntity")
        if isinstance(main_entity, (list, dict)):
            result.extend(flatten(main_entity))
        return result

    for script in soup.find_all("script", type="application/ld+json"):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        raw = raw.removeprefix("<!--").removesuffix("-->").strip()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        entities.extend(flatten(data))

    return [entity for entity in entities if isinstance(entity, dict)]


def _select_best(candidates: list[dict], scorer) -> dict | None:
    return max(candidates, key=scorer) if candidates else None


def _normalize_author(value: object) -> str:
    if isinstance(value, list):
        authors = [_normalize_author(item) for item in value]
        return ", ".join([author for author in authors if author])
    if isinstance(value, dict):
        return _coerce_text(value.get("name") or value.get("author"))
    return _coerce_text(value)


async def extract_article(url: str) -> dict:
    validate_url(url)
    fetched = await fetch_html(url, timeout=20.0)
    source_url = fetched.final_url
    html = fetched.html
    soup = BeautifulSoup(html, "html.parser")
    json_ld = _extract_json_ld_entities(soup)
    article_entity = next(
        (entity for entity in json_ld if "article" in str(entity.get("@type", "")).lower()),
        None,
    )

    doc = Document(html)
    body_html = doc.summary()
    body_text = BeautifulSoup(body_html, "html.parser").get_text(" ", strip=True)
    method = "json-ld" if article_entity else "fallback"

    if len(body_text) < 200:
        fallback_node = soup.select_one("article") or soup.select_one("main") or soup.body
        if fallback_node:
            body_html = str(fallback_node)
            body_text = fallback_node.get_text(" ", strip=True)
        method = "fallback"

    title = (
        _coerce_text((article_entity or {}).get("headline") or (article_entity or {}).get("name"))
        or _extract_meta_content(soup, "og:title", "twitter:title")
        or _clean_text(doc.title())
        or _extract_from_selectors(soup, ["article h1", "main h1", "h1"])
        or _clean_text(soup.title.string if soup.title and soup.title.string else "")
    )
    author = (
        _normalize_author((article_entity or {}).get("author"))
        or _extract_meta_content(soup, "author", "article:author")
        or _extract_from_selectors(soup, ["[itemprop='author']", "[rel='author']", ".author", ".byline"])
    )
    date = (
        _coerce_text((article_entity or {}).get("datePublished") or (article_entity or {}).get("dateModified"))
        or _extract_meta_content(soup, "article:published_time", "article:modified_time", "datePublished")
        or _extract_from_selectors(soup, ["time", "[itemprop='datePublished']"])
    )
    images = _normalize_urls((article_entity or {}).get("image"), source_url, limit=10)
    images = _dedupe(
        images
        + _extract_urls_from_selectors(BeautifulSoup(body_html, "html.parser"), ["img"], source_url, limit=20)
        + _normalize_urls(_extract_meta_content(soup, "og:image"), source_url),
        limit=20,
    )

    result = {
        "title": title,
        "author": author,
        "date": date,
        "body": body_html[:15000],
        "images": images,
        "word_count": len(body_text.split()),
        "language": soup.find("html").get("lang", "").strip() if soup.find("html") else "",
        "source_url": source_url,
    }
    result["confidence"] = {
        "title": _field_confidence(method, bool(result["title"]), 0.03),
        "body": _field_confidence(method, bool(result["body"]), 0.01),
        "author": _field_confidence(method, bool(result["author"])),
        "date": _field_confidence(method, bool(result["date"])),
    }
    return result


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("00"):
        digits = f"+{digits[2:]}"
    if digits and not digits.startswith("+") and len(re.sub(r"\D", "", digits)) >= 10:
        digits = f"+{digits}"
    return digits or phone.strip()


def _postal_address(value: object) -> str:
    if isinstance(value, dict):
        parts = [
            _coerce_text(value.get("streetAddress")),
            _coerce_text(value.get("addressLocality")),
            _coerce_text(value.get("addressRegion")),
            _coerce_text(value.get("postalCode")),
            _coerce_text(value.get("addressCountry")),
        ]
        return ", ".join([part for part in parts if part])
    if isinstance(value, list):
        return " | ".join([_postal_address(item) for item in value if _postal_address(item)])
    return _coerce_text(value)


async def extract_contact(url: str) -> dict:
    validate_url(url)
    fetched = await fetch_html(url, timeout=20.0)
    source_url = fetched.final_url
    soup = BeautifulSoup(fetched.html, "html.parser")
    json_ld = _extract_json_ld_entities(soup)
    text = soup.get_text(" ", strip=True)

    emails = {email.lower() for email in EMAIL_PATTERN.findall(text)}
    phones: set[str] = set()
    addresses: list[str] = []

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if href.startswith("mailto:"):
            emails.add(href.split(":", 1)[1].split("?", 1)[0].lower())
        elif href.startswith("tel:"):
            phones.add(_normalize_phone(href.split(":", 1)[1]))

    for raw_phone in PHONE_PATTERN.findall(text):
        normalized = _normalize_phone(raw_phone)
        if len(re.sub(r"\D", "", normalized)) >= 8:
            phones.add(normalized)

    for entity in json_ld:
        entity_type = str(entity.get("@type", "")).lower()
        if "organization" in entity_type or "business" in entity_type:
            address = _postal_address(entity.get("address"))
            if address:
                addresses.append(address)
            if entity.get("email"):
                emails.add(_coerce_text(entity["email"]).lower())
            if entity.get("telephone"):
                phones.add(_normalize_phone(_coerce_text(entity["telephone"])))

    for element in soup.find_all(attrs={"itemprop": re.compile(r"(streetAddress|address)", re.I)}):
        text_value = _clean_text(element.get("content") or element.get_text(" ", strip=True))
        if text_value:
            addresses.append(text_value)

    for address_tag in soup.find_all("address"):
        text_value = _clean_text(address_tag.get_text(" ", strip=True))
        if text_value:
            addresses.append(text_value)

    social_links: dict[str, str] = {}
    for link in soup.find_all("a", href=True):
        href = link["href"]
        for domain, label in SOCIAL_DOMAINS.items():
            if domain in href and label not in social_links:
                social_links[label] = href
                break

    emails_list = _dedupe(sorted(emails), limit=10)
    phones_list = _dedupe(sorted(phones), limit=10)
    addresses_list = _dedupe(addresses, limit=5)

    return {
        "emails": emails_list,
        "phones": phones_list,
        "addresses": addresses_list,
        "social_links": social_links,
        "source_url": source_url,
        "confidence": {
            "emails": _field_confidence("hybrid", bool(emails_list), 0.03),
            "phones": _field_confidence("hybrid", bool(phones_list), 0.01),
            "addresses": _field_confidence("hybrid", bool(addresses_list)),
            "social": _field_confidence("hybrid", bool(social_links), 0.02),
        },
    }


PRODUCT_NAME_SELECTORS = [
    "meta[property='og:title']",
    "meta[name='twitter:title']",
    "#productTitle",
    "[data-testid='product-title']",
    "[itemprop='name']",
    "main h1",
    "h1",
]
PRODUCT_PRICE_SELECTORS = [
    "meta[property='product:price:amount']",
    "meta[property='og:price:amount']",
    "[itemprop='price']",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    ".a-price .a-offscreen",
    "[data-testid='price']",
    ".product-price",
    ".price",
    ".sale-price",
]
PRODUCT_IMAGE_SELECTORS = [
    "meta[property='og:image']",
    "[itemprop='image']",
    "#landingImage",
    "#imgTagWrapperId img",
    "[data-testid*='product-image'] img",
    ".product__image img",
    "main img",
]


def _product_confidence(result: dict, method: str) -> dict:
    return {
        "name": _field_confidence(method, bool(result["name"]), 0.02),
        "price": _field_confidence(method, bool(result["price"]), 0.02),
        "images": _field_confidence(method, bool(result["images"])),
        "brand": _field_confidence(method, bool(result["brand"])),
    }


def _normalize_product_candidate(candidate: dict, base_url: str, method: str) -> dict:
    offers = candidate.get("offers")
    if isinstance(offers, list):
        offers = next((offer for offer in offers if isinstance(offer, dict)), {})
    if not isinstance(offers, dict):
        offers = {}

    aggregate_rating = candidate.get("aggregateRating")
    if isinstance(aggregate_rating, list):
        aggregate_rating = next((item for item in aggregate_rating if isinstance(item, dict)), {})
    if not isinstance(aggregate_rating, dict):
        aggregate_rating = {}

    brand = candidate.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name") or brand.get("brand")

    price, currency = _parse_price(
        offers.get("price") or candidate.get("price"),
        offers.get("priceCurrency") or candidate.get("priceCurrency") or candidate.get("currency"),
    )

    result = {
        "name": _coerce_text(candidate.get("name")),
        "price": price,
        "currency": currency,
        "description": _coerce_text(candidate.get("description")),
        "images": _normalize_urls(candidate.get("image") or candidate.get("images"), base_url, limit=10),
        "sku": _coerce_text(candidate.get("sku")),
        "brand": _coerce_text(brand),
        "availability": _strip_schema_value(offers.get("availability") or candidate.get("availability")),
        "rating": _to_float(aggregate_rating.get("ratingValue") or candidate.get("rating")),
        "review_count": _to_int(
            aggregate_rating.get("ratingCount")
            or aggregate_rating.get("reviewCount")
            or candidate.get("review_count")
            or candidate.get("reviewCount")
        ),
        "source_url": base_url,
        "extraction_method": method,
    }
    result["confidence"] = _product_confidence(result, method)
    return result


def _extract_product_microdata(soup: BeautifulSoup, base_url: str) -> list[dict]:
    products: list[dict] = []
    for item in soup.find_all(attrs={"itemtype": re.compile(r"schema\.org/Product", re.I)}):
        product: dict = {}
        for prop in ("name", "description", "sku", "brand", "image"):
            element = item.find(attrs={"itemprop": prop})
            if element:
                product[prop] = (
                    element.get("content")
                    or element.get("href")
                    or element.get("src")
                    or element.get_text(" ", strip=True)
                )
        offers = item.find(attrs={"itemprop": "offers"})
        if offers:
            product["offers"] = {}
            for prop in ("price", "priceCurrency", "availability"):
                element = offers.find(attrs={"itemprop": prop})
                if element:
                    product["offers"][prop] = (
                        element.get("content")
                        or element.get("href")
                        or element.get_text(" ", strip=True)
                    )
        products.append(_normalize_product_candidate(product, base_url, "microdata"))
    return products


def _score_product(candidate: dict) -> int:
    score = 0
    score += 5 if candidate.get("name") else 0
    score += 5 if candidate.get("price") else 0
    score += 2 if candidate.get("currency") else 0
    score += 2 if candidate.get("images") else 0
    score += 1 if candidate.get("brand") else 0
    score += 1 if candidate.get("availability") else 0
    score += 1 if candidate.get("description") else 0
    score += 1 if candidate.get("rating") is not None else 0
    score += 1 if candidate.get("review_count") is not None else 0
    return score


def _extract_product_dom(soup: BeautifulSoup, base_url: str) -> dict:
    price, currency = _parse_price(
        _extract_from_selectors(soup, PRODUCT_PRICE_SELECTORS),
        _extract_meta_content(soup, "product:price:currency", "og:price:currency"),
    )
    result = {
        "name": _extract_from_selectors(soup, PRODUCT_NAME_SELECTORS),
        "price": price,
        "currency": currency,
        "description": _extract_from_selectors(
            soup,
            ["meta[name='description']", "[itemprop='description']", "#productDescription", ".product-description"],
        ),
        "images": _extract_urls_from_selectors(soup, PRODUCT_IMAGE_SELECTORS, base_url),
        "sku": _extract_meta_content(soup, "sku"),
        "brand": _extract_from_selectors(soup, ["meta[name='brand']", "[itemprop='brand']", "#bylineInfo", ".brand"]),
        "availability": _strip_schema_value(
            _extract_from_selectors(soup, ["meta[property='product:availability']", "[itemprop='availability']", "#availability", ".availability"])
        ),
        "rating": _to_float(_extract_from_selectors(soup, ["[itemprop='ratingValue']", "span.a-icon-alt", ".rating-value"])),
        "review_count": _to_int(_extract_from_selectors(soup, ["[itemprop='ratingCount']", "[itemprop='reviewCount']", "#acrCustomerReviewText", ".review-count"])),
        "source_url": base_url,
        "extraction_method": "dom",
    }
    result["confidence"] = _product_confidence(result, "dom")
    return result


def _merge_product(primary: dict | None, secondary: dict | None) -> dict:
    merged = (primary or secondary or {}).copy()
    if primary and secondary:
        for field in ("name", "price", "currency", "description", "sku", "brand", "availability"):
            if not merged.get(field) and secondary.get(field):
                merged[field] = secondary[field]
        if merged.get("rating") is None and secondary.get("rating") is not None:
            merged["rating"] = secondary["rating"]
        if merged.get("review_count") is None and secondary.get("review_count") is not None:
            merged["review_count"] = secondary["review_count"]
        merged["images"] = _dedupe((merged.get("images") or []) + (secondary.get("images") or []), limit=10)
        if _score_product(merged) > _score_product(primary):
            merged["extraction_method"] = (
                primary.get("extraction_method")
                if primary.get("extraction_method") == secondary.get("extraction_method")
                else "hybrid"
            )
    if not merged:
        merged = {
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
            "source_url": "",
            "extraction_method": "fallback",
        }
    merged["confidence"] = _product_confidence(merged, merged.get("extraction_method", "fallback"))
    return merged


async def extract_product(url: str) -> dict:
    validate_url(url)
    fetched = await fetch_html(url, timeout=20.0)
    source_url = fetched.final_url
    soup = BeautifulSoup(fetched.html, "html.parser")

    json_ld_candidates = [
        _normalize_product_candidate(entity, source_url, "json-ld")
        for entity in _extract_json_ld_entities(soup)
        if "product" in str(entity.get("@type", "")).lower()
    ]
    microdata_candidates = _extract_product_microdata(soup, source_url)
    dom_candidate = _extract_product_dom(soup, source_url)
    structured = _select_best(json_ld_candidates + microdata_candidates, _score_product)
    merged = _merge_product(structured, dom_candidate)
    merged["source_url"] = source_url
    return merged


RECIPE_NAME_SELECTORS = ["meta[property='og:title']", "[itemprop='name']", "article h1", "main h1", "h1"]
RECIPE_IMAGE_SELECTORS = ["meta[property='og:image']", "[itemprop='image']", ".recipe-image img", "article img"]


def _extract_recipe_steps(value: object) -> list[str]:
    steps: list[str] = []

    def collect(item: object) -> None:
        if isinstance(item, list):
            for sub_item in item:
                collect(sub_item)
            return
        if isinstance(item, dict):
            if item.get("@type") == "HowToSection":
                collect(item.get("itemListElement"))
                return
            text = _coerce_text(item.get("text") or item.get("name"))
            if text:
                steps.append(text)
            else:
                collect(item.get("itemListElement"))
            return
        text = _coerce_text(item)
        if text:
            steps.append(text)

    collect(value)
    return _dedupe(steps, limit=30)


def _recipe_confidence(result: dict, method: str) -> dict:
    return {
        "name": _field_confidence(method, bool(result["name"]), 0.02),
        "ingredients": _field_confidence(method, bool(result["ingredients"]), 0.02),
        "instructions": _field_confidence(method, bool(result["instructions"]), 0.01),
    }


def _normalize_recipe_candidate(candidate: dict, base_url: str, method: str) -> dict:
    nutrition = candidate.get("nutrition") if isinstance(candidate.get("nutrition"), dict) else {}
    aggregate_rating = candidate.get("aggregateRating")
    if isinstance(aggregate_rating, list):
        aggregate_rating = next((item for item in aggregate_rating if isinstance(item, dict)), {})
    if not isinstance(aggregate_rating, dict):
        aggregate_rating = {}
    ingredients = candidate.get("recipeIngredient") or candidate.get("ingredients") or []
    if isinstance(ingredients, str):
        ingredients = [ingredients]

    result = {
        "name": _coerce_text(candidate.get("name")),
        "description": _coerce_text(candidate.get("description")),
        "author": _normalize_author(candidate.get("author")),
        "prep_time": _coerce_text(candidate.get("prepTime")),
        "cook_time": _coerce_text(candidate.get("cookTime")),
        "total_time": _coerce_text(candidate.get("totalTime")),
        "servings": _coerce_text(candidate.get("recipeYield")),
        "ingredients": _dedupe([_coerce_text(item) for item in ingredients], limit=50),
        "instructions": _extract_recipe_steps(candidate.get("recipeInstructions")),
        "images": _normalize_urls(candidate.get("image"), base_url, limit=10),
        "cuisine": _coerce_text(candidate.get("recipeCuisine")),
        "category": _coerce_text(candidate.get("recipeCategory")),
        "calories": _coerce_text(nutrition.get("calories") or candidate.get("calories")),
        "rating": _to_float(aggregate_rating.get("ratingValue") or candidate.get("rating")),
        "review_count": _to_int(aggregate_rating.get("ratingCount") or aggregate_rating.get("reviewCount") or candidate.get("reviewCount")),
        "source_url": base_url,
        "extraction_method": method,
    }
    result["confidence"] = _recipe_confidence(result, method)
    return result


def _extract_recipe_microdata(soup: BeautifulSoup, base_url: str) -> list[dict]:
    recipes: list[dict] = []
    for item in soup.find_all(attrs={"itemtype": re.compile(r"schema\.org/Recipe", re.I)}):
        recipe: dict = {}
        for prop in ("name", "description", "author", "prepTime", "cookTime", "totalTime", "recipeYield", "recipeCuisine", "recipeCategory"):
            element = item.find(attrs={"itemprop": prop})
            if element:
                recipe[prop] = element.get("content") or element.get("datetime") or element.get_text(" ", strip=True)
        recipe["recipeIngredient"] = [
            element.get("content") or element.get_text(" ", strip=True)
            for element in item.find_all(attrs={"itemprop": "recipeIngredient"})
        ]
        recipe["recipeInstructions"] = [
            element.get_text(" ", strip=True)
            for element in item.find_all(attrs={"itemprop": "recipeInstructions"})
        ]
        recipes.append(_normalize_recipe_candidate(recipe, base_url, "microdata"))
    return recipes


def _extract_recipe_dom(soup: BeautifulSoup, base_url: str) -> dict:
    result = {
        "name": _extract_from_selectors(soup, RECIPE_NAME_SELECTORS),
        "description": _extract_from_selectors(soup, ["meta[name='description']", "[itemprop='description']", ".recipe-summary"]),
        "author": _extract_from_selectors(soup, ["[itemprop='author']", ".author", ".byline"]),
        "prep_time": _extract_from_selectors(soup, ["[itemprop='prepTime']"]),
        "cook_time": _extract_from_selectors(soup, ["[itemprop='cookTime']"]),
        "total_time": _extract_from_selectors(soup, ["[itemprop='totalTime']"]),
        "servings": _extract_from_selectors(soup, ["[itemprop='recipeYield']", ".recipe-yield"]),
        "ingredients": _dedupe(
            [
                _clean_text(element.get("content") or element.get_text(" ", strip=True))
                for selector in ("[itemprop='recipeIngredient']", ".recipe-ingredients li", ".ingredients li")
                for element in soup.select(selector)
            ],
            limit=50,
        ),
        "instructions": _dedupe(
            [
                _clean_text(element.get_text(" ", strip=True))
                for selector in ("[itemprop='recipeInstructions'] li", ".recipe-instructions li", ".instructions li", "ol li")
                for element in soup.select(selector)
            ],
            limit=30,
        ),
        "images": _extract_urls_from_selectors(soup, RECIPE_IMAGE_SELECTORS, base_url),
        "cuisine": _extract_from_selectors(soup, ["[itemprop='recipeCuisine']"]),
        "category": _extract_from_selectors(soup, ["[itemprop='recipeCategory']"]),
        "calories": _extract_from_selectors(soup, ["[itemprop='calories']"]),
        "rating": _to_float(_extract_from_selectors(soup, ["[itemprop='ratingValue']", ".rating-value"])),
        "review_count": _to_int(_extract_from_selectors(soup, ["[itemprop='ratingCount']", "[itemprop='reviewCount']"])),
        "source_url": base_url,
        "extraction_method": "dom",
    }
    result["confidence"] = _recipe_confidence(result, "dom")
    return result


def _score_recipe(candidate: dict) -> int:
    score = 0
    score += 5 if candidate.get("name") else 0
    score += 4 if candidate.get("ingredients") else 0
    score += 4 if candidate.get("instructions") else 0
    score += 2 if candidate.get("images") else 0
    score += 1 if candidate.get("description") else 0
    score += 1 if candidate.get("total_time") else 0
    return score


def _merge_recipe(primary: dict | None, secondary: dict | None) -> dict:
    merged = (primary or secondary or {}).copy()
    if primary and secondary:
        for field in ("name", "description", "author", "prep_time", "cook_time", "total_time", "servings", "cuisine", "category", "calories"):
            if not merged.get(field) and secondary.get(field):
                merged[field] = secondary[field]
        if merged.get("rating") is None and secondary.get("rating") is not None:
            merged["rating"] = secondary["rating"]
        if merged.get("review_count") is None and secondary.get("review_count") is not None:
            merged["review_count"] = secondary["review_count"]
        merged["ingredients"] = _dedupe((merged.get("ingredients") or []) + (secondary.get("ingredients") or []), limit=50)
        merged["instructions"] = _dedupe((merged.get("instructions") or []) + (secondary.get("instructions") or []), limit=30)
        merged["images"] = _dedupe((merged.get("images") or []) + (secondary.get("images") or []), limit=10)
        if _score_recipe(merged) > _score_recipe(primary):
            merged["extraction_method"] = (
                primary.get("extraction_method")
                if primary.get("extraction_method") == secondary.get("extraction_method")
                else "hybrid"
            )
    if not merged:
        merged = {
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
            "source_url": "",
            "extraction_method": "fallback",
        }
    merged["confidence"] = _recipe_confidence(merged, merged.get("extraction_method", "fallback"))
    return merged


async def extract_recipe(url: str) -> dict:
    validate_url(url)
    fetched = await fetch_html(url, timeout=20.0)
    source_url = fetched.final_url
    soup = BeautifulSoup(fetched.html, "html.parser")

    json_ld_candidates = [
        _normalize_recipe_candidate(entity, source_url, "json-ld")
        for entity in _extract_json_ld_entities(soup)
        if "recipe" in str(entity.get("@type", "")).lower()
    ]
    microdata_candidates = _extract_recipe_microdata(soup, source_url)
    dom_candidate = _extract_recipe_dom(soup, source_url)
    structured = _select_best(json_ld_candidates + microdata_candidates, _score_recipe)
    merged = _merge_recipe(structured, dom_candidate)
    merged["source_url"] = source_url
    return merged
