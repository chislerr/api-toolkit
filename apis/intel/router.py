import httpx
from fastapi import APIRouter, HTTPException
from .service import full_audit, _check_security_headers, _detect_tech_stack, _get_client
from bs4 import BeautifulSoup
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
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(request.url)
            headers = dict(response.headers)
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
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(request.url)
            headers = dict(response.headers)
            html = response.text
        soup = BeautifulSoup(html, "html.parser")
        technologies = _detect_tech_stack(soup, headers, html)
        return {"technologies": technologies, "source_url": request.url}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to detect technology stack")
