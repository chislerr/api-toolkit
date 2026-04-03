import pytest
import respx
from httpx import AsyncClient, ASGITransport, Response
from main import app

API_KEY = "dev-api-key-change-me"
HEADERS = {"X-API-Key": API_KEY}

SAMPLE_HTML_WITH_JSONLD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Test Article</title>
    <meta name="description" content="A test article for structured data validation">
    <meta property="og:title" content="Test Article">
    <meta property="og:description" content="A test article">
    <meta property="og:image" content="https://example.com/image.jpg">
    <meta property="og:type" content="article">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Test Article">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "Test Article Title",
        "image": "https://example.com/image.jpg",
        "datePublished": "2026-01-15T08:00:00+00:00",
        "author": {
            "@type": "Person",
            "name": "John Doe"
        },
        "description": "A comprehensive test article."
    }
    </script>
</head>
<body>
    <h1>Test Article Title</h1>
    <p>This is the body of the test article.</p>
</body>
</html>
"""

SAMPLE_HTML_NO_SD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Plain Page</title>
</head>
<body>
    <h1>No structured data here</h1>
</body>
</html>
"""

SAMPLE_HTML_PRODUCT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Product Page</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Test Widget",
        "image": "https://example.com/widget.jpg",
        "description": "A great widget",
        "brand": { "@type": "Brand", "name": "WidgetCo" },
        "offers": {
            "@type": "Offer",
            "price": "29.99",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.5",
            "bestRating": "5",
            "ratingCount": "120"
        }
    }
    </script>
</head>
<body>
    <h1>Test Widget</h1>
</body>
</html>
"""


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ─── Auth Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seo_auth_required(client):
    response = await client.post(
        "/v1/seo/structured-data", json={"url": "https://example.com"}
    )
    assert response.status_code == 401


# ─── /v1/seo/structured-data ─────────────────────────────────────


@pytest.mark.asyncio
async def test_structured_data_with_url(client):
    with respx.mock:
        respx.get("https://example.com").mock(return_value=Response(200, text=SAMPLE_HTML_WITH_JSONLD))
        response = await client.post(
            "/v1/seo/structured-data",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "json_ld" in data
    assert "microdata" in data
    assert "open_graph" in data
    assert "twitter_card" in data
    assert "meta_tags" in data
    assert "summary" in data
    assert "source_url" in data


@pytest.mark.asyncio
async def test_structured_data_summary_fields(client):
    with respx.mock:
        respx.get("https://example.com").mock(return_value=Response(200, text=SAMPLE_HTML_WITH_JSONLD))
        response = await client.post(
            "/v1/seo/structured-data",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert "total_entities" in summary
    assert "types_found" in summary
    assert "rich_results_eligible" in summary
    assert "overall_score" in summary
    assert "critical_errors" in summary
    assert "warnings" in summary


# ─── /v1/seo/rich-results ────────────────────────────────────────


@pytest.mark.asyncio
async def test_rich_results_with_url(client):
    with respx.mock:
        respx.get("https://example.com").mock(return_value=Response(200, text=SAMPLE_HTML_WITH_JSONLD))
        response = await client.post(
            "/v1/seo/rich-results",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "eligible" in data
    assert "not_eligible" in data
    assert "summary" in data
    assert isinstance(data["eligible"], list)
    assert isinstance(data["not_eligible"], list)


@pytest.mark.asyncio
async def test_rich_results_summary(client):
    with respx.mock:
        respx.get("https://example.com").mock(return_value=Response(200, text=SAMPLE_HTML_WITH_JSONLD))
        response = await client.post(
            "/v1/seo/rich-results",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert "eligible_count" in summary
    assert "total_types_checked" in summary
    assert "types_checked" in summary
    assert summary["total_types_checked"] == 18


# ─── /v1/seo/validate-html ───────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_html_with_article(client):
    response = await client.post(
        "/v1/seo/validate-html",
        json={"html": SAMPLE_HTML_WITH_JSONLD},
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert "json_ld" in data
    assert "summary" in data
    assert data["summary"]["total_entities"] >= 1
    assert "Article" in data["summary"]["types_found"]


@pytest.mark.asyncio
async def test_validate_html_no_structured_data(client):
    response = await client.post(
        "/v1/seo/validate-html",
        json={"html": SAMPLE_HTML_NO_SD},
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_entities"] == 0
    assert data["summary"]["overall_score"] == 0.0


@pytest.mark.asyncio
async def test_validate_html_product_eligible(client):
    response = await client.post(
        "/v1/seo/validate-html",
        json={"html": SAMPLE_HTML_PRODUCT},
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert "Product" in data["summary"]["types_found"]
    assert "Product" in data["summary"]["rich_results_eligible"]


@pytest.mark.asyncio
async def test_validate_html_fix_suggestions(client):
    response = await client.post(
        "/v1/seo/validate-html",
        json={"html": SAMPLE_HTML_WITH_JSONLD},
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    json_ld = data["json_ld"]
    assert len(json_ld) >= 1
    validation = json_ld[0].get("_validation", {})
    warnings = validation.get("warnings", [])
    if warnings:
        assert any(w.get("fix") for w in warnings)


# ─── /v1/seo/health-score ────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_score_structure(client):
    with respx.mock:
        respx.get("https://example.com").mock(return_value=Response(200, text=SAMPLE_HTML_WITH_JSONLD))
        response = await client.post(
            "/v1/seo/health-score",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "score" in data
    assert "grade" in data
    assert "breakdown" in data
    assert "top_fixes" in data
    assert 0 <= data["score"] <= 100
    assert data["grade"] in ("A", "B", "C", "D", "F")


@pytest.mark.asyncio
async def test_health_score_breakdown(client):
    with respx.mock:
        respx.get("https://example.com").mock(return_value=Response(200, text=SAMPLE_HTML_WITH_JSONLD))
        response = await client.post(
            "/v1/seo/health-score",
            json={"url": "https://example.com"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    breakdown = response.json()["breakdown"]
    assert "structured_data_present" in breakdown
    assert "json_ld_count" in breakdown
    assert "microdata_count" in breakdown
    assert "has_open_graph" in breakdown
    assert "has_twitter_card" in breakdown
    assert "rich_results_eligible" in breakdown
    assert "rich_results_total" in breakdown
    assert "critical_errors" in breakdown
    assert "warnings" in breakdown


# ─── Error Handling ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_html_empty_html(client):
    response = await client.post(
        "/v1/seo/validate-html",
        json={"html": "<html><body></body></html>"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_entities"] == 0


@pytest.mark.asyncio
async def test_seo_invalid_url(client):
    response = await client.post(
        "/v1/seo/structured-data",
        json={"url": "not-a-valid-url"},
        headers=HEADERS,
    )
    assert response.status_code == 422
