import socket

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from core.models import PdfFromHtmlRequest
from core.ssrf import validate_url
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
async def test_auth_required_extract(client):
    response = await client.post("/v1/extract/article", json={"url": "https://example.com"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_required_intel(client):
    response = await client.post("/v1/intel/audit", json={"url": "https://example.com"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_required_seo(client):
    response = await client.post("/v1/seo/structured-data", json={"url": "https://example.com"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_required_tools(client):
    response = await client.post("/v1/tools/html-to-markdown", json={"url": "https://example.com"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_success(client):
    response = await client.get("/health", headers={"X-API-Key": "dev-api-key-change-me"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_request_id_header(client):
    response = await client.get("/health")
    assert "x-request-id" in response.headers


@pytest.mark.asyncio
async def test_openapi_schema(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    for path in schema["paths"]:
        assert path.startswith("/v1/") or path in ("/health", "/ready", "/")


def test_ssrf_rejects_any_private_resolution(monkeypatch):
    def fake_getaddrinfo(host, port, type=0):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(Exception):
        validate_url("https://example.com")


def test_pdf_margin_validation():
    with pytest.raises(ValidationError):
        PdfFromHtmlRequest(html="<p>Hello</p>", margin_top="12")
