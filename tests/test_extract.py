import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from main import app

API_KEY = "dev-api-key-change-me"
HEADERS = {"X-API-Key": API_KEY}

ARTICLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Platform Engineering at Scale</title>
  <meta property="og:title" content="Platform Engineering at Scale" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Platform Engineering at Scale",
    "datePublished": "2026-04-01",
    "author": {"@type": "Person", "name": "Jane Doe"},
    "image": "/images/cover.jpg"
  }
  </script>
</head>
<body>
  <article>
    <h1>Platform Engineering at Scale</h1>
    <p>Teams that ship quickly need a platform that lowers cognitive load and removes repetitive toil.</p>
    <p>That means standard paved roads, reliable automation, and clear ownership boundaries across services.</p>
    <img src="/images/inline.jpg" />
  </article>
</body>
</html>
"""

CONTACT_HTML = """
<!DOCTYPE html>
<html>
<head><title>Contact</title></head>
<body>
  <a href="mailto:sales@example.com">sales@example.com</a>
  <a href="tel:+1 (555) 123-4567">Call</a>
  <address>123 Main St, Springfield, IL 62701</address>
  <a href="https://linkedin.com/company/example">LinkedIn</a>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    "email": "support@example.com",
    "telephone": "+1-555-987-6543",
    "address": {
      "@type": "PostalAddress",
      "streetAddress": "500 Market St",
      "addressLocality": "San Francisco",
      "addressRegion": "CA",
      "postalCode": "94105",
      "addressCountry": "US"
    }
  }
  </script>
</body>
</html>
"""

PRODUCT_HYBRID_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Noise Cancelling Headphones</title>
  <meta property="og:image" content="/images/headphones-og.jpg" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Product",
        "name": "Noise Cancelling Headphones",
        "brand": {"@type": "Brand", "name": "QuietCo"},
        "image": ["/images/headphones-1.jpg"],
        "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.7", "ratingCount": "1234"}
      }
    ]
  }
  </script>
</head>
<body>
  <h1 id="productTitle">Noise Cancelling Headphones</h1>
  <span id="priceblock_ourprice">$299.99</span>
  <div id="availability">In Stock</div>
  <span id="acrCustomerReviewText">1234 ratings</span>
</body>
</html>
"""

PRODUCT_DOM_ONLY_HTML = """
<!DOCTYPE html>
<html>
<head><title>Travel Backpack</title></head>
<body>
  <h1 id="productTitle">Travel Backpack 40L</h1>
  <span class="a-price"><span class="a-offscreen">$89.50</span></span>
  <div id="imgTagWrapperId"><img data-old-hires="https://example.com/images/backpack.jpg" /></div>
  <div id="availability"><span>Only 3 left in stock</span></div>
  <a id="bylineInfo">TrailWorks</a>
</body>
</html>
"""

RECIPE_GRAPH_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Weekend Pancakes</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Recipe",
        "name": "Weekend Pancakes",
        "recipeIngredient": ["2 cups flour", "2 eggs", "1 cup milk"],
        "recipeInstructions": [
          {"@type": "HowToSection", "itemListElement": [
            {"@type": "HowToStep", "text": "Whisk the dry ingredients."},
            {"@type": "HowToStep", "text": "Fold in the wet ingredients."}
          ]},
          {"@type": "HowToStep", "text": "Cook on a skillet until golden."}
        ],
        "image": "/images/pancakes.jpg",
        "recipeYield": "4 servings"
      }
    ]
  }
  </script>
</head>
<body><article><h1>Weekend Pancakes</h1></article></body>
</html>
"""


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_extract_article_returns_real_fields(client):
    with respx.mock:
        respx.get("https://example.com/article").mock(return_value=Response(200, text=ARTICLE_HTML))
        response = await client.post("/v1/extract/article", json={"url": "https://example.com/article"}, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Platform Engineering at Scale"
    assert data["author"] == "Jane Doe"
    assert data["date"] == "2026-04-01"
    assert data["word_count"] > 10
    assert "https://example.com/images/cover.jpg" in data["images"]


@pytest.mark.asyncio
async def test_extract_contact_combines_links_and_json_ld(client):
    with respx.mock:
        respx.get("https://example.com/contact").mock(return_value=Response(200, text=CONTACT_HTML))
        response = await client.post("/v1/extract/contact", json={"url": "https://example.com/contact"}, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert "sales@example.com" in data["emails"]
    assert "support@example.com" in data["emails"]
    assert any(phone.endswith("5551234567") for phone in data["phones"])
    assert any("500 Market St" in address for address in data["addresses"])
    assert data["social_links"]["linkedin"] == "https://linkedin.com/company/example"


@pytest.mark.asyncio
async def test_extract_product_merges_json_ld_and_dom_signals(client):
    with respx.mock:
        respx.get("https://example.com/product").mock(return_value=Response(200, text=PRODUCT_HYBRID_HTML))
        response = await client.post("/v1/extract/product", json={"url": "https://example.com/product"}, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Noise Cancelling Headphones"
    assert data["price"] == "299.99"
    assert data["currency"] == "USD"
    assert data["brand"] == "QuietCo"
    assert data["review_count"] == 1234
    assert data["extraction_method"] in {"hybrid", "json-ld"}
    assert data["images"]


@pytest.mark.asyncio
async def test_extract_product_dom_fallback_handles_amazon_like_markup(client):
    with respx.mock:
        respx.get("https://example.com/backpack").mock(return_value=Response(200, text=PRODUCT_DOM_ONLY_HTML))
        response = await client.post("/v1/extract/product", json={"url": "https://example.com/backpack"}, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Travel Backpack 40L"
    assert data["price"] == "89.50"
    assert data["currency"] == "USD"
    assert data["brand"] == "TrailWorks"
    assert data["images"] == ["https://example.com/images/backpack.jpg"]
    assert "stock" in data["availability"].lower()


@pytest.mark.asyncio
async def test_extract_recipe_handles_graph_and_howto_sections(client):
    with respx.mock:
        respx.get("https://example.com/recipe").mock(return_value=Response(200, text=RECIPE_GRAPH_HTML))
        response = await client.post("/v1/extract/recipe", json={"url": "https://example.com/recipe"}, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Weekend Pancakes"
    assert len(data["ingredients"]) == 3
    assert data["instructions"][0] == "Whisk the dry ingredients."
    assert data["images"] == ["https://example.com/images/pancakes.jpg"]


@pytest.mark.asyncio
async def test_extract_blocks_ssrf_redirects(client):
    with respx.mock:
        respx.get("https://example.com/redirect").mock(return_value=Response(302, headers={"location": "http://localhost:8000/private"}))
        response = await client.post("/v1/extract/article", json={"url": "https://example.com/redirect"}, headers=HEADERS)

    assert response.status_code == 400
