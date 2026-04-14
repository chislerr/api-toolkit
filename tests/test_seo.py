import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from main import app

API_KEY = "dev-api-key-change-me"
HEADERS = {"X-API-Key": API_KEY}

ARTICLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Test Article</title>
  <meta name="description" content="A test article">
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
    "author": {"@type": "Person", "name": "John Doe"},
    "description": "A comprehensive test article."
  }
  </script>
</head>
<body><h1>Test Article Title</h1></body>
</html>
"""

COMPLETE_PRODUCT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Widget Page</title>
  <meta name="description" content="A complete product page">
  <meta property="og:title" content="Widget Page">
  <meta property="og:description" content="A complete product page">
  <meta property="og:image" content="https://example.com/widget.jpg">
  <meta property="og:type" content="product">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="canonical" href="https://example.com/widget">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Test Widget",
    "image": "https://example.com/widget.jpg",
    "description": "A great widget",
    "brand": { "@type": "Brand", "name": "WidgetCo" },
    "sku": "WIDGET-01",
    "gtin": "0123456789012",
    "offers": {
      "@type": "Offer",
      "price": "29.99",
      "priceCurrency": "USD",
      "availability": "https://schema.org/InStock",
      "url": "https://example.com/widget"
    },
    "aggregateRating": {
      "@type": "AggregateRating",
      "ratingValue": "4.5",
      "bestRating": "5",
      "ratingCount": "120",
      "reviewCount": "95"
    },
    "review": {
      "@type": "Review",
      "reviewRating": { "@type": "Rating", "ratingValue": "5" },
      "author": { "@type": "Person", "name": "Jane" }
    }
  }
  </script>
</head>
<body><h1>Test Widget</h1></body>
</html>
"""

FAQ_BROKEN_HTML = """
<!DOCTYPE html>
<html>
<head>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {
        "@type": "Question",
        "name": "What is this?",
        "acceptedAnswer": {"@type": "Answer"}
      }
    ]
  }
  </script>
</head>
<body></body>
</html>
"""

PLAIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>Plain Page</title></head>
<body><h1>No structured data here</h1></body>
</html>
"""


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_seo_auth_required(client):
    response = await client.post("/v1/seo/structured-data", json={"url": "https://example.com"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_structured_data_extracts_validation_summary(client):
    with respx.mock:
        respx.get("https://example.com/article").mock(return_value=Response(200, text=ARTICLE_HTML))
        response = await client.post("/v1/seo/structured-data", json={"url": "https://example.com/article"}, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_entities"] == 1
    assert "Article" in data["summary"]["types_found"]
    assert "Article" in data["summary"]["rich_results_eligible"]


@pytest.mark.asyncio
async def test_validate_html_reports_nested_faq_answer_problem(client):
    response = await client.post("/v1/seo/validate-html", json={"html": FAQ_BROKEN_HTML}, headers=HEADERS)
    assert response.status_code == 200
    validation = response.json()["json_ld"][0]["_validation"]
    assert any("acceptedAnswer.text" in issue["field"] for issue in validation["errors"])


@pytest.mark.asyncio
async def test_rich_results_reports_nested_offer_fields(client):
    incomplete_product = COMPLETE_PRODUCT_HTML.replace('"priceCurrency": "USD",', "")
    with respx.mock:
        respx.get("https://example.com/product").mock(return_value=Response(200, text=incomplete_product))
        response = await client.post("/v1/seo/rich-results", json={"url": "https://example.com/product"}, headers=HEADERS)

    assert response.status_code == 200
    product_entry = next(entry for entry in response.json()["not_eligible"] if entry["type"] == "Product")
    assert "offers.priceCurrency" in product_entry["fields_missing"]


@pytest.mark.asyncio
async def test_health_score_rewards_complete_relevant_schema(client):
    with respx.mock:
        respx.get("https://example.com/widget").mock(return_value=Response(200, text=COMPLETE_PRODUCT_HTML))
        response = await client.post("/v1/seo/health-score", json={"url": "https://example.com/widget"}, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["score"] >= 80
    assert data["breakdown"]["rich_results_total"] == 1
    assert data["breakdown"]["rich_results_eligible"] == 1


@pytest.mark.asyncio
async def test_health_score_plain_page_stays_low_and_suggests_schema(client):
    with respx.mock:
        respx.get("https://example.com/plain").mock(return_value=Response(200, text=PLAIN_HTML))
        response = await client.post("/v1/seo/health-score", json={"url": "https://example.com/plain"}, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["score"] < 30
    assert any("JSON-LD" in fix or '"headline"' in fix or '"name"' in fix for fix in data["top_fixes"])


@pytest.mark.asyncio
async def test_seo_invalid_url(client):
    response = await client.post("/v1/seo/structured-data", json={"url": "not-a-valid-url"}, headers=HEADERS)
    assert response.status_code == 422
