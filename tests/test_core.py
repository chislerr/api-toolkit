import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_root(client):
    response = await client.get("/")
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "docs" in data


@pytest.mark.asyncio
async def test_auth_required(client):
    """Endpoints should require API key."""
    response = await client.post("/pdf/from-url", json={"url": "https://example.com"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_success(client):
    """Valid API key should pass auth."""
    response = await client.get(
        "/health",
        headers={"X-API-Key": "dev-api-key-change-me"},
    )
    assert response.status_code == 200
