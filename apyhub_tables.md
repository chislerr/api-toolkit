# ApyHub API Submission Reference

All endpoints are prefixed with `/v1/`. Base URL: `https://api-toolkit-yb1l.onrender.com`

---

## 1. Structured Data Validator API

**Category**: SEO
**Recommended Price**: 100 atoms

### POST /v1/seo/structured-data

Extract and validate all schema.org structured data from a URL.

**Request Body:**
| Attribute | Type | Mandatory | Description |
|-----------|------|-----------|-------------|
| url | String | Yes | URL to extract structured data from (http/https only, max 2048 chars) |

**Response:**
```json
{
  "url": "https://example.com",
  "json_ld": [
    {
      "@type": "Article",
      "headline": "Test Article",
      "_validation": {
        "type": "Article",
        "rich_result_category": "Article",
        "errors": [],
        "warnings": [{"field": "dateModified", "message": "Missing recommended field 'dateModified'", "severity": "warning", "fix": "\"dateModified\": \"<ISO 8601 date>\""}],
        "score": 0.85
      }
    }
  ],
  "microdata": [],
  "open_graph": {"og:title": "Example", "og:description": "Desc", "og:image": "https://example.com/img.jpg"},
  "twitter_card": {"twitter:card": "summary_large_image"},
  "meta_tags": {"title": "Example", "description": "Desc", "canonical": "https://example.com"},
  "summary": {
    "total_entities": 1,
    "types_found": ["Article"],
    "rich_results_eligible": ["Article"],
    "overall_score": 0.85,
    "critical_errors": 0,
    "warnings": 1
  },
  "source_url": "https://example.com"
}
```

### POST /v1/seo/rich-results

Check Google Rich Results eligibility across 18 types.

**Request Body:** Same as above.

**Response:**
```json
{
  "url": "https://example.com",
  "eligible": [{"type": "Article", "status": "eligible", "fields_present": ["headline", "image"], "fields_missing": [], "fields_recommended": ["dateModified"]}],
  "not_eligible": [{"type": "Product", "status": "not_found", "fields_present": [], "fields_missing": ["name", "image"], "fields_recommended": ["description"]}],
  "summary": {"eligible_count": 1, "total_types_checked": 18, "types_checked": ["Article", "Product", "Recipe", ...]},
  "source_url": "https://example.com"
}
```

### POST /v1/seo/validate-html

Validate structured data from raw HTML (no URL fetch).

**Request Body:**
| Attribute | Type | Mandatory | Description |
|-----------|------|-----------|-------------|
| html | String | Yes | Raw HTML content (max 5,000,000 chars) |

**Response:** Same structure as `/structured-data`.

### POST /v1/seo/health-score

Overall structured data health score (0-100) with letter grade and fix suggestions.

**Request Body:** Same as `/structured-data`.

**Response:**
```json
{
  "url": "https://example.com",
  "score": 75,
  "grade": "B",
  "breakdown": {
    "structured_data_present": true,
    "json_ld_count": 1,
    "microdata_count": 0,
    "has_open_graph": true,
    "has_twitter_card": true,
    "rich_results_eligible": 1,
    "rich_results_total": 18,
    "critical_errors": 0,
    "warnings": 1
  },
  "top_fixes": ["\"dateModified\": \"<ISO 8601 date>\"", ...],
  "source_url": "https://example.com"
}
```

---

## 2. Data Extractor API

**Category**: Data Extraction
**Recommended Price**: 100 atoms per endpoint

### POST /v1/extract/article

Extract main article content from a web page.

**Request Body:**
| Attribute | Type | Mandatory | Description |
|-----------|------|-----------|-------------|
| url | String | Yes | URL of the article (http/https, max 2048 chars) |

**Response:**
```json
{
  "title": "Article Title",
  "author": "John Doe",
  "date": "2026-01-15",
  "body": "<p>Article body HTML...</p>",
  "images": ["https://example.com/img.jpg"],
  "word_count": 1250,
  "language": "en",
  "source_url": "https://example.com/article",
  "confidence": {"title": 0.9, "body": 0.85, "author": 0.7}
}
```

### POST /v1/extract/contact

Extract contact information from a web page.

**Request Body:** Same as above.

**Response:**
```json
{
  "emails": ["contact@example.com"],
  "phones": ["+1-555-123-4567"],
  "addresses": ["123 Main St"],
  "social_links": {"facebook": "https://facebook.com/page", "twitter": "https://twitter.com/page"},
  "source_url": "https://example.com/contact",
  "confidence": {"emails": 0.95, "phones": 0.85, "social": 0.9}
}
```

### POST /v1/extract/product

Extract product details from an e-commerce page.

**Request Body:** Same as above.

**Response:**
```json
{
  "name": "Test Widget",
  "price": "29.99",
  "currency": "USD",
  "description": "A great widget",
  "images": ["https://example.com/widget.jpg"],
  "sku": "WGT-001",
  "brand": "WidgetCo",
  "availability": "https://schema.org/InStock",
  "rating": 4.5,
  "review_count": 120,
  "source_url": "https://example.com/product",
  "extraction_method": "json-ld",
  "confidence": {"name": 0.95, "price": 0.9}
}
```

### POST /v1/extract/recipe

Extract recipe data from a cooking page.

**Request Body:** Same as above.

**Response:**
```json
{
  "name": "Easy Pancakes",
  "description": "Fluffy homemade pancakes",
  "author": "Jane Smith",
  "prep_time": "PT10M",
  "cook_time": "PT15M",
  "total_time": "PT25M",
  "servings": "4",
  "ingredients": ["1 cup flour", "2 eggs", "1 cup milk"],
  "instructions": ["Mix dry ingredients", "Add wet ingredients", "Cook on griddle"],
  "images": ["https://example.com/pancakes.jpg"],
  "cuisine": "American",
  "category": "Breakfast",
  "calories": "250",
  "rating": 4.8,
  "review_count": 45,
  "source_url": "https://example.com/recipe",
  "extraction_method": "json-ld",
  "confidence": {"name": 0.95, "ingredients": 0.9}
}
```

---

## 3. Website Intelligence API

**Category**: Data Extraction / Security
**Recommended Price**: 100 atoms (audit), 50 atoms (headers/techstack)

### POST /v1/intel/audit

Full website audit: meta tags, tech stack, security headers, performance, broken links, mobile-friendliness.

**Request Body:**
| Attribute | Type | Mandatory | Description |
|-----------|------|-----------|-------------|
| url | String | Yes | Target website URL (http/https, max 2048 chars) |

**Response:**
```json
{
  "url": "https://example.com",
  "meta_tags": {"title": "Example", "description": "Description", "canonical": "https://example.com", "og_title": "Example", "og_description": "Description", "og_image": "https://example.com/og.jpg", "twitter_card": "summary_large_image"},
  "tech_stack": ["Nginx", "React", "Google Analytics"],
  "security_headers": {"has_hsts": true, "has_csp": false, "has_x_frame_options": true, "has_x_content_type": true, "has_referrer_policy": false, "score": "C", "details": {"strict-transport-security": "Present", "content-security-policy": "Missing"}},
  "performance": {"page_size_bytes": 45000, "page_size_readable": "43.9 KB", "load_time_ms": 320, "num_requests": 15},
  "broken_links": [],
  "is_mobile_friendly": true,
  "source_url": "https://example.com"
}
```

### POST /v1/intel/headers

Check HTTP security headers and get a security grade (A-F).

**Request Body:** Same as above.

**Response:**
```json
{
  "has_hsts": true,
  "has_csp": false,
  "has_x_frame_options": true,
  "has_x_content_type": true,
  "has_referrer_policy": false,
  "score": "C",
  "details": {"strict-transport-security": "Present", "content-security-policy": "Missing"}
}
```

### POST /v1/intel/techstack

Detect technology stack (frameworks, CMS, analytics, hosting).

**Request Body:** Same as above.

**Response:**
```json
{
  "technologies": ["Cloudflare", "React", "Google Analytics", "Google Fonts"],
  "source_url": "https://example.com"
}
```

---

## 4. Dynamic OG Image API

**Category**: Image Processing / Marketing
**Recommended Price**: 30 atoms

### POST /v1/tools/og-image

Generate a 1200x630 Open Graph image (PNG).

**Request Body:**
| Attribute | Type | Mandatory | Description |
|-----------|------|-----------|-------------|
| title | String | Yes | Main headline (max 200 chars) |
| subtitle | String | No | Subtitle text (max 300 chars) |
| bg_color | String | No | Hex background color (default: #1a202c) |
| text_color | String | No | Hex text color (default: #ffffff) |
| accent_color | String | No | Hex accent color (auto-derived if omitted) |
| template | String | No | Template: blog, minimal, bold, card (default: blog) |
| background | String | No | Background: solid, gradient, gradient_horizontal, gradient_vertical, pattern, mesh (default: solid) |
| author | String | No | Author name (max 100 chars) |
| tag | String | No | Tag/label pill text (max 50 chars) |
| domain | String | No | Domain name to display (max 100 chars) |
| reading_time | String | No | Reading time label (max 50 chars) |

**Response:** Raw PNG image (`Content-Type: image/png`, `Cache-Control: max-age=86400`)

**cURL Example:**
```bash
curl -X POST "https://api-toolkit-yb1l.onrender.com/v1/tools/og-image" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title":"My Blog Post","subtitle":"A great article","bg_color":"#4f46e5","template":"blog"}' \
  --output og-image.png
```

---

## 5. Clean HTML to Markdown API

**Category**: Data Extraction / File Conversion
**Recommended Price**: 50 atoms

### POST /v1/tools/html-to-markdown

Fetch a webpage, extract main content, convert to clean Markdown.

**Request Body:**
| Attribute | Type | Mandatory | Description |
|-----------|------|-----------|-------------|
| url | String | Yes | URL to convert (http/https, max 2048 chars) |

**Response:**
```json
{
  "title": "Article Title",
  "markdown": "# Article Title\n\nThis is the cleaned markdown content...",
  "character_count": 15420,
  "readability_success": true
}
```

---

## Error Responses

All endpoints return consistent error format:

**400 Bad Request (SSRF/Validation):**
```json
{"detail": "Access to 'localhost' is not allowed."}
```

**401 Unauthorized:**
```json
{"error": "unauthorized", "detail": "Valid X-API-Key header required"}
```

**422 Validation Error:**
```json
{"detail": [{"type": "value_error", "loc": ["body", "url"], "msg": "URL must start with http:// or https://"}]}
```

**429 Rate Limited:**
```json
{"error": "rate_limited", "detail": "Too many requests. Please slow down and try again later."}
```

**500 Internal Error:**
```json
{"detail": "Failed to extract article content"}
```

---

## Authentication

All endpoints require `X-API-Key` header.

```bash
curl -H "X-API-Key: YOUR_API_KEY" https://api-toolkit-yb1l.onrender.com/v1/...
```

## Rate Limiting

100 requests per minute per API key. Response includes `X-RateLimit-Remaining` header.

## Request Tracing

Every response includes `X-Request-ID` header for debugging and log correlation.
