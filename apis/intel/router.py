from fastapi import APIRouter, HTTPException
from core.models import IntelAuditRequest, IntelAuditResponse, SecurityHeaders, MetaTags
from apis.intel.service import audit_site, _check_security_headers, _extract_meta_tags, _detect_tech_stack
import httpx
from bs4 import BeautifulSoup

router = APIRouter()


@router.post(
    "/audit",
    response_model=IntelAuditResponse,
    summary="Full website audit",
    description=(
        "Run a comprehensive website intelligence audit in one call. "
        "Returns meta tags, detected tech stack, security header score, "
        "broken links, performance metrics, and mobile-friendliness."
    ),
)
async def api_audit(request: IntelAuditRequest):
    try:
        result = await audit_site(request.url)
        return IntelAuditResponse(**result)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Target site returned HTTP {e.response.status_code}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")


@router.post(
    "/headers",
    response_model=SecurityHeaders,
    summary="Security headers analysis",
    description="Check a URL's HTTP security headers and get a grade (A-F).",
)
async def api_headers(request: IntelAuditRequest):
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
            response = await client.get(request.url)
            headers = dict(response.headers)
        result = _check_security_headers(headers)
        return SecurityHeaders(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Headers check failed: {str(e)}")


@router.post(
    "/techstack",
    summary="Detect technology stack",
    description="Detect the technology stack used by a website (frameworks, CMS, analytics, etc).",
)
async def api_techstack(request: IntelAuditRequest):
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
            response = await client.get(request.url)
            html = response.text
            headers = dict(response.headers)
        soup = BeautifulSoup(html, "lxml")
        techs = _detect_tech_stack(soup, html, headers)
        return {"url": request.url, "technologies": techs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tech detection failed: {str(e)}")
