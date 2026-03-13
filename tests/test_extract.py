import pytest
from httpx import AsyncClient, ASGITransport
from main import app

API_KEY = "dev-api-key-change-me"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_extract_article(client):
    """Test article extraction on a known stable page."""
    response = await client.post(
        "/extract/article",
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
    """Test contact extraction."""
    response = await client.post(
        "/extract/contact",
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
    """Test product extraction."""
    response = await client.post(
        "/extract/product",
        json={"url": "https://example.com"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "price" in data
