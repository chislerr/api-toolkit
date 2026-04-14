from fastapi import APIRouter, HTTPException
from .service import full_audit, _check_security_headers, _detect_tech_stack
from bs4 import BeautifulSoup
from core.fetch import fetch_html
from core.models import (
    IntelAuditRequest,
    IntelAuditResponse,
    SecurityHeaders,
)
from core.ssrf import validate_url

router = APIRouter()


@router.post(
    "/audit",
    response_model=IntelAuditResponse,
    summary="Full website audit",
    description="Perform a comprehensive website audit including meta tags, tech stack detection, security headers, performance metrics, broken link checking, and mobile-friendliness.",
)
async def api_full_audit(request: IntelAuditRequest):
    try:
        result = await full_audit(request.url)
        return IntelAuditResponse(**result)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to perform website audit")


@router.post(
    "/headers",
    response_model=SecurityHeaders,
    summary="Check security headers",
    description="Analyze a website's HTTP security headers and provide a security grade (A-F).",
)
async def api_security_headers(request: IntelAuditRequest):
    try:
        validate_url(request.url)
        fetched = await fetch_html(request.url, timeout=15.0)
        headers = fetched.headers
        result = _check_security_headers(headers)
        return SecurityHeaders(**result)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to check security headers")


@router.post(
    "/techstack",
    summary="Detect technology stack",
    description="Detect the technology stack used by a website (frameworks, CMS, analytics, etc).",
)
async def api_techstack(request: IntelAuditRequest):
    try:
        validate_url(request.url)
        fetched = await fetch_html(request.url, timeout=15.0)
        headers = fetched.headers
        html = fetched.html
        soup = BeautifulSoup(html, "html.parser")
        technologies = _detect_tech_stack(soup, headers, html)
        return {"technologies": technologies, "source_url": fetched.final_url}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to detect technology stack")
