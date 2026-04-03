import httpx

BASE = "http://127.0.0.1:8765"
KEY = {"X-API-Key": "dev-api-key-change-me"}

print("=== Smoke Test Suite ===\n")

# 1. SSRF block
r = httpx.post(f"{BASE}/v1/extract/article", json={"url": "http://localhost:8000/health"}, headers=KEY, timeout=10)
print(f"1. SSRF block (localhost): {r.status_code} {r.json()}")
assert r.status_code == 400

# 2. Invalid URL
r = httpx.post(f"{BASE}/v1/extract/article", json={"url": "not-a-url"}, headers=KEY, timeout=10)
print(f"2. Invalid URL: {r.status_code}")
assert r.status_code == 422

# 3. OG Image
r = httpx.post(f"{BASE}/v1/tools/og-image", json={"title": "Test"}, headers=KEY, timeout=10)
print(f"3. OG Image: {r.status_code} type={r.headers.get('content-type')} size={len(r.content)}")
assert r.status_code == 200
assert "image/png" in r.headers.get("content-type", "")

# 4. SEO validate-html
html = '<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"Article","headline":"Test"}</script></head><body></body></html>'
r = httpx.post(f"{BASE}/v1/seo/validate-html", json={"html": html}, headers=KEY, timeout=10)
data = r.json()
print(f"4. SEO validate: {r.status_code} entities={data['summary']['total_entities']} types={data['summary']['types_found']}")
assert r.status_code == 200
assert data["summary"]["total_entities"] >= 1

# 5. Intel headers (hits real network)
try:
    r = httpx.post(f"{BASE}/v1/intel/headers", json={"url": "https://example.com"}, headers=KEY, timeout=30)
    print(f"5. Intel headers: {r.status_code} score={r.json().get('score')}")
except Exception as e:
    print(f"5. Intel headers: SKIPPED (network) - {e}")

# 6. Rate limit header
r = httpx.get(f"{BASE}/health", headers=KEY, timeout=10)
print(f"6. Rate limit remaining: {r.headers.get('x-ratelimit-remaining')}")

# 7. Request ID
print(f"7. Request ID: {r.headers.get('x-request-id')}")
assert r.headers.get("x-request-id") is not None

# 8. Auth required
r = httpx.post(f"{BASE}/v1/tools/og-image", json={"title": "Test"}, timeout=10)
print(f"8. Auth required: {r.status_code}")
assert r.status_code == 401

# 9. OpenAPI schema has /v1/ prefix
r = httpx.get(f"{BASE}/openapi.json", timeout=10)
paths = list(r.json()["paths"].keys())
v1_paths = [p for p in paths if p.startswith("/v1/")]
print(f"9. OpenAPI /v1/ paths: {len(v1_paths)} total")
assert len(v1_paths) >= 10

# 10. Health
r = httpx.get(f"{BASE}/health", timeout=10)
print(f"10. Health: {r.status_code} {r.json()}")
assert r.status_code == 200

print("\n=== ALL SMOKE TESTS PASSED ===")
