import pytest
from httpx import AsyncClient, ASGITransport
from main import app

API_KEY = "dev-api-key-change-me"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ─── OG Image Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_og_image_basic(client):
    response = await client.post(
        "/v1/tools/og-image",
        json={
            "title": "Test Blog Post",
            "subtitle": "A test subtitle",
            "bg_color": "#4f46e5",
        },
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 0


@pytest.mark.asyncio
async def test_og_image_all_templates(client):
    for template in ["blog", "minimal", "bold", "card"]:
        response = await client.post(
            "/v1/tools/og-image",
            json={
                "title": f"Template Test: {template}",
                "template": template,
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_og_image_all_backgrounds(client):
    for bg in ["solid", "gradient", "gradient_horizontal", "gradient_vertical", "pattern", "mesh"]:
        response = await client.post(
            "/v1/tools/og-image",
            json={
                "title": "Background Test",
                "background": bg,
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_og_image_with_meta(client):
    response = await client.post(
        "/v1/tools/og-image",
        json={
            "title": "Full Meta Test",
            "subtitle": "With all optional fields",
            "author": "Jane Doe",
            "domain": "example.com",
            "reading_time": "5 min read",
            "tag": "Tutorial",
            "accent_color": "#10b981",
        },
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_og_image_cache_header(client):
    response = await client.post(
        "/v1/tools/og-image",
        json={"title": "Cache Test"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert "max-age=86400" in response.headers.get("cache-control", "")


@pytest.mark.asyncio
async def test_og_image_missing_title(client):
    response = await client.post(
        "/v1/tools/og-image",
        json={},
        headers=HEADERS,
    )
    assert response.status_code == 422


# ─── HTML to Markdown Tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_html_to_markdown_invalid_url(client):
    response = await client.post(
        "/v1/tools/html-to-markdown",
        json={"url": "not-a-url"},
        headers=HEADERS,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_html_to_markdown_missing_url(client):
    response = await client.post(
        "/v1/tools/html-to-markdown",
        json={},
        headers=HEADERS,
    )
    assert response.status_code == 422
