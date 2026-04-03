import logging
import re
import httpx
from bs4 import BeautifulSoup
from readability import Document
from core.ssrf import validate_url

logger = logging.getLogger("api-toolkit.extract")

# ─── HTTP Client ──────────────────────────────────────────────────


def _get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        },
    )


# ─── Helpers ──────────────────────────────────────────────────────


def _extract_meta_tags(soup: BeautifulSoup) -> dict:
    meta = {}
    for tag in soup.find_all("meta"):
        name = tag.get("name") or tag.get("property") or tag.get("itemprop")
        if name:
            meta[name] = tag.get("content", "")
    return meta


def _extract_json_ld(soup: BeautifulSoup) -> list:
    results = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            import json
            data = json.loads(script.string)
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)
        except (json.JSONDecodeError, TypeError):
            continue
    return results


def _extract_product_microdata(soup: BeautifulSoup) -> list:
    products = []
    for item in soup.find_all(attrs={"itemtype": re.compile(r'schema\.org/Product')}):
        product = {}
        for prop in ["name", "image", "description", "sku", "brand"]:
            el = item.find(attrs={"itemprop": prop})
            if el:
                product[prop] = el.get_text(strip=True) or el.get("content", "")
        offers = item.find(attrs={"itemprop": "offers"})
        if offers:
            price_el = offers.find(attrs={"itemprop": "price"})
            if price_el:
                product["price"] = price_el.get("content", "") or price_el.get_text(strip=True)
            currency_el = offers.find(attrs={"itemprop": "priceCurrency"})
            if currency_el:
                product["currency"] = currency_el.get("content", "")
            avail_el = offers.find(attrs={"itemprop": "availability"})
            if avail_el:
                product["availability"] = avail_el.get("content", "")
        products.append(product)
    return products


def _extract_recipe_microdata(soup: BeautifulSoup) -> list:
    recipes = []
    for item in soup.find_all(attrs={"itemtype": re.compile(r'schema\.org/Recipe')}):
        recipe = {}
        for prop in ["name", "description", "author", "prepTime", "cookTime",
                     "totalTime", "recipeYield", "recipeCuisine", "recipeCategory", "calories"]:
            el = item.find(attrs={"itemprop": prop})
            if el:
                recipe[prop] = el.get_text(strip=True) or el.get("content", "")
        ingredients = item.find(attrs={"itemprop": "recipeIngredient"})
        if ingredients:
            recipe["ingredients"] = [
                ing.get_text(strip=True)
                for ing in item.find_all(attrs={"itemprop": "recipeIngredient"})
            ]
        instructions = item.find(attrs={"itemprop": "recipeInstructions"})
        if instructions:
            if instructions.find_all("li"):
                recipe["instructions"] = [
                    li.get_text(strip=True) for li in instructions.find_all("li")
                ]
            else:
                recipe["instructions"] = [instructions.get_text(strip=True)]
        recipes.append(recipe)
    return recipes


# ─── Extraction Functions ─────────────────────────────────────────


async def extract_article(url: str) -> dict:
    """Extract main article content from a URL."""
    validate_url(url)
    async with _get_client() as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text

    soup = BeautifulSoup(html, "html.parser")
    doc = Document(html)

    title = doc.title() or soup.find("title").get_text(strip=True) if soup.find("title") else ""
    body = doc.summary()

    author = ""
    author_meta = soup.find("meta", attrs={"name": "author"})
    if author_meta:
        author = author_meta.get("content", "")
    else:
        author_el = soup.find(attrs={"itemprop": "author"})
        if author_el:
            author = author_el.get_text(strip=True)

    date = ""
    date_el = soup.find("time")
    if date_el:
        date = date_el.get("datetime", "") or date_el.get_text(strip=True)
    else:
        date_meta = soup.find("meta", attrs={"property": "article:published_time"})
        if date_meta:
            date = date_meta.get("content", "")

    images = []
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if src.startswith("http"):
            images.append(src)
        elif src.startswith("//"):
            images.append(f"https:{src}")
        elif src.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            images.append(f"{parsed.scheme}://{parsed.netloc}{src}")
    images = images[:20]

    body_text = BeautifulSoup(body, "html.parser").get_text()
    word_count = len(body_text.split())
    language = soup.find("html").get("lang", "") if soup.find("html") else ""

    return {
        "title": title,
        "author": author,
        "date": date,
        "body": body[:10000],
        "images": images,
        "word_count": word_count,
        "language": language,
        "source_url": url,
        "confidence": {"title": 0.9, "body": 0.85, "author": 0.7 if author else 0.0},
    }


async def extract_contact(url: str) -> dict:
    """Extract contact information from a URL."""
    validate_url(url)
    async with _get_client() as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()

    emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)))[:10]

    phone_patterns = [
        r'\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
        r'\+\d{1,3}[\s.-]?\d{3,}[\s.-]?\d{3,}[\s.-]?\d{4,}',
    ]
    phones = []
    for pattern in phone_patterns:
        phones.extend(re.findall(pattern, text))
    phones = list(set(phones))[:10]

    addresses = []
    for meta in soup.find_all("meta", attrs={"itemprop": "address"}):
        content = meta.get("content", "")
        if content:
            addresses.append(content)
    for el in soup.find_all(attrs={"itemprop": "streetAddress"}):
        content = el.get_text(strip=True)
        if content:
            addresses.append(content)
    addresses = addresses[:5]

    social_links = {}
    social_domains = ["facebook.com", "twitter.com", "x.com", "linkedin.com",
                      "instagram.com", "youtube.com", "tiktok.com", "github.com"]
    for link in soup.find_all("a", href=True):
        href = link["href"]
        for domain in social_domains:
            if domain in href:
                social_links[domain.split(".")[0]] = href
                break
    social_links = dict(list(social_links.items())[:10])

    return {
        "emails": emails,
        "phones": phones,
        "addresses": addresses,
        "social_links": social_links,
        "source_url": url,
        "confidence": {
            "emails": 0.95 if emails else 0.0,
            "phones": 0.85 if phones else 0.0,
            "social": 0.9 if social_links else 0.0,
        },
    }


async def extract_product(url: str) -> dict:
    """Extract product information from an e-commerce page."""
    validate_url(url)
    async with _get_client() as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text

    soup = BeautifulSoup(html, "html.parser")

    product = {}
    json_ld_items = _extract_json_ld(soup)
    for item in json_ld_items:
        if item.get("@type") == "Product" or "Product" in str(item.get("@type", "")):
            product = item
            break

    if product:
        name = product.get("name", "")
        if isinstance(name, list):
            name = name[0] if name else ""

        offers = product.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        price = str(offers.get("price", ""))
        currency = offers.get("priceCurrency", "")
        availability = offers.get("availability", "")

        brand = product.get("brand", "")
        if isinstance(brand, dict):
            brand = brand.get("name", "")

        rating = None
        review_count = None
        agg_rating = product.get("aggregateRating", {})
        if isinstance(agg_rating, dict):
            try:
                rating = float(agg_rating.get("ratingValue", 0))
                review_count = int(agg_rating.get("ratingCount", 0))
            except (ValueError, TypeError):
                pass

        images = product.get("image", [])
        if isinstance(images, str):
            images = [images]

        result = {
            "name": name,
            "price": price,
            "currency": currency,
            "description": product.get("description", ""),
            "images": images[:10],
            "sku": product.get("sku", ""),
            "brand": brand,
            "availability": availability,
            "rating": rating,
            "review_count": review_count,
            "source_url": url,
            "extraction_method": "json-ld",
            "confidence": {
                "name": 0.95 if name else 0.0,
                "price": 0.9 if price else 0.0,
            },
        }

        if name or price:
            return result

    microdata_products = _extract_product_microdata(soup)
    if microdata_products:
        p = microdata_products[0]
        return {
            "name": p.get("name", ""),
            "price": p.get("price", ""),
            "currency": p.get("currency", ""),
            "description": p.get("description", ""),
            "images": [p["image"]] if p.get("image") else [],
            "sku": p.get("sku", ""),
            "brand": p.get("brand", ""),
            "availability": p.get("availability", ""),
            "rating": None,
            "review_count": None,
            "source_url": url,
            "extraction_method": "microdata",
            "confidence": {
                "name": 0.85 if p.get("name") else 0.0,
                "price": 0.8 if p.get("price") else 0.0,
            },
        }

    title = soup.find("title").get_text(strip=True) if soup.find("title") else ""
    og_title = ""
    og_price = ""
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "")
        if prop == "og:title":
            og_title = meta.get("content", "")
        elif prop == "product:price:amount":
            og_price = meta.get("content", "")

    return {
        "name": og_title or title,
        "price": og_price,
        "currency": "",
        "description": "",
        "images": [],
        "sku": "",
        "brand": "",
        "availability": "",
        "rating": None,
        "review_count": None,
        "source_url": url,
        "extraction_method": "fallback",
        "confidence": {"name": 0.4, "price": 0.3 if og_price else 0.0},
    }


async def extract_recipe(url: str) -> dict:
    """Extract recipe information from a cooking page."""
    validate_url(url)
    async with _get_client() as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text

    soup = BeautifulSoup(html, "html.parser")

    recipe = {}
    json_ld_items = _extract_json_ld(soup)
    for item in json_ld_items:
        if item.get("@type") == "Recipe" or "Recipe" in str(item.get("@type", "")):
            recipe = item
            break

    if recipe:
        name = recipe.get("name", "")
        if isinstance(name, list):
            name = name[0] if name else ""

        ingredients = recipe.get("recipeIngredient", recipe.get("ingredients", []))
        if isinstance(ingredients, str):
            ingredients = [ingredients]

        instructions_raw = recipe.get("recipeInstructions", [])
        if isinstance(instructions_raw, str):
            instructions = [instructions_raw]
        elif isinstance(instructions_raw, list):
            instructions = []
            for step in instructions_raw:
                if isinstance(step, dict):
                    instructions.append(step.get("text", step.get("name", "")))
                elif isinstance(step, str):
                    instructions.append(step)
        else:
            instructions = []

        nutrition = recipe.get("nutrition", {})
        if isinstance(nutrition, dict):
            calories = nutrition.get("calories", "")
        else:
            calories = ""

        rating = None
        review_count = None
        agg_rating = recipe.get("aggregateRating", {})
        if isinstance(agg_rating, dict):
            try:
                rating = float(agg_rating.get("ratingValue", 0))
                review_count = int(agg_rating.get("ratingCount", 0))
            except (ValueError, TypeError):
                pass

        images = recipe.get("image", [])
        if isinstance(images, str):
            images = [images]

        return {
            "name": name,
            "description": recipe.get("description", ""),
            "author": recipe.get("author", {}).get("name", "") if isinstance(recipe.get("author"), dict) else str(recipe.get("author", "")),
            "prep_time": recipe.get("prepTime", ""),
            "cook_time": recipe.get("cookTime", ""),
            "total_time": recipe.get("totalTime", ""),
            "servings": str(recipe.get("recipeYield", "")),
            "ingredients": ingredients[:50],
            "instructions": instructions[:20],
            "images": images[:10],
            "cuisine": recipe.get("recipeCuisine", ""),
            "category": recipe.get("recipeCategory", ""),
            "calories": str(calories),
            "rating": rating,
            "review_count": review_count,
            "source_url": url,
            "extraction_method": "json-ld",
            "confidence": {
                "name": 0.95 if name else 0.0,
                "ingredients": 0.9 if ingredients else 0.0,
            },
        }

    microdata_recipes = _extract_recipe_microdata(soup)
    if microdata_recipes:
        r = microdata_recipes[0]
        return {
            "name": r.get("name", ""),
            "description": r.get("description", ""),
            "author": r.get("author", ""),
            "prep_time": r.get("prepTime", ""),
            "cook_time": r.get("cookTime", ""),
            "total_time": r.get("totalTime", ""),
            "servings": r.get("recipeYield", ""),
            "ingredients": r.get("ingredients", [])[:50],
            "instructions": r.get("instructions", [])[:20],
            "images": [],
            "cuisine": r.get("recipeCuisine", ""),
            "category": r.get("recipeCategory", ""),
            "calories": r.get("calories", ""),
            "rating": None,
            "review_count": None,
            "source_url": url,
            "extraction_method": "microdata",
            "confidence": {
                "name": 0.85 if r.get("name") else 0.0,
                "ingredients": 0.8 if r.get("ingredients") else 0.0,
            },
        }

    title = soup.find("title").get_text(strip=True) if soup.find("title") else ""
    return {
        "name": title,
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
        "source_url": url,
        "extraction_method": "fallback",
        "confidence": {"name": 0.3, "ingredients": 0.0},
    }
