from io import BytesIO

import pytest
import respx
from PIL import Image
from httpx import ASGITransport, AsyncClient, Response

from main import app

API_KEY = "dev-api-key-change-me"
HEADERS = {"X-API-Key": API_KEY}

MARKDOWN_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Shipping Distributed Systems</title>
</head>
<body>
  <nav><a href="/home">Home</a></nav>
  <main>
    <article>
      <h1>Shipping Distributed Systems</h1>
      <p>Distributed systems reward clear interfaces, durable contracts, and disciplined operational thinking.</p>
      <p>Strong observability, explicit retries, and principled fallbacks turn partial failure from chaos into a known state.</p>
      <p>That is the difference between a demo and a system customers trust during real incidents.</p>
      <img src="/images/diagram.png" />
      <a href="/guide">Read the guide</a>
    </article>
  </main>
  <footer>Footer links</footer>
</body>
</html>
"""


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_og_image_basic_dimensions(client):
    response = await client.post(
        "/v1/tools/og-image",
        json={"title": "Test Blog Post", "subtitle": "A test subtitle", "bg_color": "#4f46e5"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    image = Image.open(BytesIO(response.content))
    assert image.size == (1200, 630)


@pytest.mark.asyncio
async def test_og_image_invalid_colors_fallback_safely(client):
    response = await client.post(
        "/v1/tools/og-image",
        json={"title": "Fallback Colors", "bg_color": "not-a-color", "text_color": "still-bad"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_og_image_missing_title(client):
    response = await client.post("/v1/tools/og-image", json={}, headers=HEADERS)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_html_to_markdown_cleans_boilerplate_and_resolves_relative_urls(client):
    with respx.mock:
        respx.get("https://example.com/story").mock(return_value=Response(200, text=MARKDOWN_HTML))
        response = await client.post(
            "/v1/tools/html-to-markdown",
            json={"url": "https://example.com/story"},
            headers=HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Shipping Distributed Systems"
    assert "Distributed systems reward clear interfaces" in data["markdown"]
    assert "Footer links" not in data["markdown"]
    assert "https://example.com/images/diagram.png" in data["markdown"]
    assert "https://example.com/guide" in data["markdown"]


@pytest.mark.asyncio
async def test_html_to_markdown_invalid_url(client):
    response = await client.post(
        "/v1/tools/html-to-markdown",
        json={"url": "not-a-url"},
        headers=HEADERS,
    )
    assert response.status_code == 422
