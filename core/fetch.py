import asyncio
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from fastapi import HTTPException

from core.ssrf import validate_url

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(slots=True)
class FetchResult:
    html: str
    final_url: str
    headers: dict[str, str]
    status_code: int


def build_async_client(
    *,
    timeout: float = 20.0,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        headers=merged_headers,
    )


async def fetch_html(
    url: str,
    *,
    timeout: float = 20.0,
    max_redirects: int = 5,
    retries: int = 1,
    max_bytes: int = 3_000_000,
    headers: dict[str, str] | None = None,
) -> FetchResult:
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        current_url = validate_url(url)

        try:
            async with build_async_client(timeout=timeout, headers=headers) as client:
                should_retry = False

                for redirect_count in range(max_redirects + 1):
                    response = await client.get(current_url)

                    if (
                        response.status_code in REDIRECT_STATUS_CODES
                        and "location" in response.headers
                    ):
                        if redirect_count >= max_redirects:
                            raise HTTPException(
                                status_code=502,
                                detail="Too many redirects while fetching the URL.",
                            )
                        current_url = validate_url(
                            urljoin(str(response.request.url), response.headers["location"])
                        )
                        continue

                    if (
                        response.status_code in RETRYABLE_STATUS_CODES
                        and attempt < retries
                    ):
                        should_retry = True
                        break

                    response.raise_for_status()

                    final_url = validate_url(str(response.url))
                    content_type = response.headers.get("content-type", "").lower()
                    looks_like_html = response.text.lstrip().startswith("<")
                    if content_type and not any(
                        item in content_type for item in HTML_CONTENT_TYPES
                    ) and not looks_like_html:
                        raise HTTPException(
                            status_code=415,
                            detail=(
                                "Fetched content is not HTML. "
                                f"Received content type '{content_type}'."
                            ),
                        )

                    if len(response.content) > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail="Fetched page is too large to process safely.",
                        )

                    return FetchResult(
                        html=response.text,
                        final_url=final_url,
                        headers=dict(response.headers),
                        status_code=response.status_code,
                    )

                if should_retry:
                    await asyncio.sleep(0.25 * (attempt + 1))
                    continue
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if (
                exc.response is not None
                and exc.response.status_code in RETRYABLE_STATUS_CODES
                and attempt < retries
            ):
                await asyncio.sleep(0.25 * (attempt + 1))
                continue
            status_code = exc.response.status_code if exc.response is not None else 502
            raise HTTPException(
                status_code=status_code,
                detail=f"Failed to fetch URL: upstream returned HTTP {status_code}.",
            ) from exc
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(0.25 * (attempt + 1))
                continue
            break

    raise HTTPException(
        status_code=502,
        detail=f"Failed to fetch URL: {last_error or 'network error'}",
    )
