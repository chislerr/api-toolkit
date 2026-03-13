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
async def test_intel_audit(client):
    """Test full site audit."""
    response = await client.post(
        "/intel/audit",
        json={"url": "https://example.com"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert "meta_tags" in data
    assert "tech_stack" in data
    assert "security_headers" in data
    assert "performance" in data
    assert "broken_links" in data


@pytest.mark.asyncio
async def test_intel_headers(client):
    """Test security headers check."""
    response = await client.post(
        "/intel/headers",
        json={"url": "https://example.com"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "has_hsts" in data


@pytest.mark.asyncio
async def test_intel_techstack(client):
    """Test tech stack detection."""
    response = await client.post(
        "/intel/techstack",
        json={"url": "https://example.com"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert "technologies" in data
    assert isinstance(data["technologies"], list)
