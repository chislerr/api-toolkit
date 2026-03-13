# API Toolkit

A portfolio of high-value APIs for developers: PDF generation, data extraction, and website intelligence.

## APIs

| API | Endpoint | Description |
|-----|----------|-------------|
| **PDF Converter** | `POST /pdf/from-url` | Convert any URL to PDF |
| | `POST /pdf/from-html` | Convert HTML string to PDF |
| **Data Extractor** | `POST /extract/article` | Extract article content (title, author, body) |
| | `POST /extract/contact` | Extract emails, phones, social links |
| | `POST /extract/product` | Extract product data (name, price, images) |
| **Website Intelligence** | `POST /intel/audit` | Full site audit (SEO, security, tech stack) |
| | `POST /intel/headers` | Security headers analysis (A-F grade) |
| | `POST /intel/techstack` | Technology stack detection |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run locally
uvicorn main:app --reload --port 8000

# Or use Docker
docker build -t api-toolkit .
docker run -p 8000:8000 api-toolkit
```

## Authentication

All endpoints require an `X-API-Key` header:

```bash
curl -X POST http://localhost:8000/intel/techstack \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

## Docs

Interactive API docs at `/docs` (Swagger UI) or `/redoc`.

## Deploy

**Render:** Connect your repo and it auto-deploys from `render.yaml`.

**Railway:** Connect your repo — auto-detects the Dockerfile.

**Docker:**
```bash
docker build -t api-toolkit .
docker run -e API_KEY=your-secret-key -p 8000:8000 api-toolkit
```

## License

MIT
