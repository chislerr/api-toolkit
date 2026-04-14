import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from main import app

API_KEY = "dev-api-key-change-me"
HEADERS = {"X-API-Key": API_KEY}

AUDIT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Shop Example</title>
  <meta name="description" content="A test shop">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta property="og:title" content="Shop Example">
  <link rel="canonical" href="/canonical-page">
  <script>window.__NEXT_DATA__ = {};</script>
  <script src="https://cdn.shopify.com/s/files/theme.js"></script>
</head>
<body>
  <a href="/ok">OK</a>
  <a href="/head-fallback">Fallback</a>
  <a href="/broken">Broken</a>
</body>
</html>
"""


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_intel_audit_detects_broken_links_and_meta(client):
    with respx.mock:
        respx.route(method="GET", url__regex=r"^https://example\.com/?$").mock(
            return_value=Response(200, text=AUDIT_HTML, headers={"Server": "cloudflare"})
        )
        respx.head("https://example.com/ok").mock(return_value=Response(200))
        respx.head("https://example.com/head-fallback").mock(return_value=Response(405))
        respx.get("https://example.com/head-fallback").mock(return_value=Response(404))
        respx.head("https://example.com/broken").mock(return_value=Response(404))

        response = await client.post("/v1/intel/audit", json={"url": "https://example.com"}, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["meta_tags"]["canonical"] == "https://example.com/canonical-page"
    assert data["is_mobile_friendly"] is True
    assert "https://example.com/head-fallback" in data["broken_links"]
    assert "https://example.com/broken" in data["broken_links"]


@pytest.mark.asyncio
async def test_intel_headers_returns_grade_and_details(client):
    with respx.mock:
        respx.get("https://example.com").mock(
            return_value=Response(
                200,
                text="<html></html>",
                headers={
                    "Strict-Transport-Security": "max-age=31536000",
                    "Content-Security-Policy": "default-src 'self'",
                    "X-Frame-Options": "DENY",
                    "Referrer-Policy": "same-origin",
                },
            )
        )
        response = await client.post("/v1/intel/headers", json={"url": "https://example.com"}, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["score"] in {"B", "A"}
    assert data["details"]["strict-transport-security"] == "max-age=31536000"


@pytest.mark.asyncio
async def test_intel_techstack_detects_framework_and_platform_signals(client):
    with respx.mock:
        respx.get("https://example.com").mock(
            return_value=Response(200, text=AUDIT_HTML, headers={"Server": "cloudflare", "x-shopid": "123"})
        )
        response = await client.post("/v1/intel/techstack", json={"url": "https://example.com"}, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert "Next.js" in data["technologies"]
    assert "Shopify" in data["technologies"]
    assert "Cloudflare" in data["technologies"]


@pytest.mark.asyncio
async def test_intel_invalid_url(client):
    response = await client.post("/v1/intel/audit", json={"url": "ftp://example.com"}, headers=HEADERS)
    assert response.status_code == 422
