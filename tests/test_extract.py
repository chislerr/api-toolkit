import pytest
import respx
from httpx import AsyncClient, ASGITransport, Response
from main import app

API_KEY = "dev-api-key-change-me"
HEADERS = {"X-API-Key": API_KEY}

SAMPLE_ARTICLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>Test Article</title><meta name="author" content="John Doe"></head>
<body>
<article><h1>Test Article</h1><p>This is the body of the test article with enough words to count properly for the word count test.</p></article>
</body>
</html>
"""

SAMPLE_CONTACT_HTML = """
<!DOCTYPE html>
<html><head><title>Contact Page</title></head>
<body>
<p>Email us at test@example.com or call +1-555-123-4567</p>
<a href="https://facebook.com/testpage">Facebook</a>
</body>
</html>
"""

SAMPLE_PRODUCT_HTML = """
<!DOCTYPE html>
<html><head><title>Product Page</title>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Test Widget","offers":{"@type":"Offer","price":"29.99","priceCurrency":"USD"}}
</script>
</head><body><h1>Test Widget</h1></body>
</html>
"""

SAMPLE_RECIPE_HTML = """
<!DOCTYPE html>
<html><head><title>Recipe Page</title>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Recipe","name":"Test Pancakes","recipeIngredient":["Flour","Eggs","Milk"],"recipeInstructions":"Mix and cook"}
</script>
</head><body><h1>Test Pancakes</h1></body>
</html>
"""


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_extract_article(client):
    with respx.mock:
        respx.get("https://example.com").mock(return_value=Response(200, text=SAMPLE_ARTICLE_HTML))
        response = await client.post(
            "/v1/extract/article",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "body" in data
    assert "source_url" in data


@pytest.mark.asyncio
async def test_extract_contact(client):
    with respx.mock:
        respx.get("https://example.com").mock(return_value=Response(200, text=SAMPLE_CONTACT_HTML))
        response = await client.post(
            "/v1/extract/contact",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert "emails" in data
    assert "phones" in data
    assert "social_links" in data


@pytest.mark.asyncio
async def test_extract_product(client):
    with respx.mock:
        respx.get("https://example.com").mock(return_value=Response(200, text=SAMPLE_PRODUCT_HTML))
        response = await client.post(
            "/v1/extract/product",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "price" in data


@pytest.mark.asyncio
async def test_extract_recipe(client):
    with respx.mock:
        respx.get("https://example.com").mock(return_value=Response(200, text=SAMPLE_RECIPE_HTML))
        response = await client.post(
            "/v1/extract/recipe",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "ingredients" in data


@pytest.mark.asyncio
async def test_extract_invalid_url(client):
    response = await client.post(
        "/v1/extract/article",
        json={"url": "not-a-url"},
        headers=HEADERS,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_extract_blocked_ssrf_url(client):
    response = await client.post(
        "/v1/extract/article",
        json={"url": "http://localhost:8000/health"},
        headers=HEADERS,
    )
    assert response.status_code == 400
