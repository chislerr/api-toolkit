import pytest
import respx
from httpx import AsyncClient, ASGITransport, Response
from main import app

API_KEY = "dev-api-key-change-me"
HEADERS = {"X-API-Key": API_KEY}

SAMPLE_AUDIT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Test Site</title>
    <meta name="description" content="A test site">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta property="og:title" content="Test Site">
    <link rel="canonical" href="https://example.com">
</head>
<body><h1>Hello</h1></body>
</html>
"""


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_intel_audit(client):
    with respx.mock:
        respx.get("https://example.com").mock(
            return_value=Response(200, text=SAMPLE_AUDIT_HTML, headers={"Server": "nginx"})
        )
        response = await client.post(
            "/v1/intel/audit",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert "meta_tags" in data
    assert "tech_stack" in data
    assert "security_headers" in data
    assert "performance" in data


@pytest.mark.asyncio
async def test_intel_headers(client):
    with respx.mock:
        respx.get("https://example.com").mock(
            return_value=Response(200, text="<html></html>", headers={
                "Strict-Transport-Security": "max-age=31536000",
                "X-Frame-Options": "DENY",
            })
        )
        response = await client.post(
            "/v1/intel/headers",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert data["has_hsts"] is True
    assert data["has_x_frame_options"] is True


@pytest.mark.asyncio
async def test_intel_techstack(client):
    with respx.mock:
        respx.get("https://example.com").mock(
            return_value=Response(200, text=SAMPLE_AUDIT_HTML, headers={"Server": "cloudflare"})
        )
        response = await client.post(
            "/v1/intel/techstack",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert "technologies" in data
    assert isinstance(data["technologies"], list)


@pytest.mark.asyncio
async def test_intel_invalid_url(client):
    response = await client.post(
        "/v1/intel/audit",
        json={"url": "ftp://example.com"},
        headers=HEADERS,
    )
    assert response.status_code == 422
