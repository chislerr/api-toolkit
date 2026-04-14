import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import HTTPException

ALLOWED_SCHEMES = {"http", "https"}

BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
    "169.254.169.254",
}


def validate_url(url: str) -> str:
    """Validate a URL for SSRF protection. Returns the URL if valid, raises HTTPException otherwise."""
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid URL scheme: '{parsed.scheme}'. Only http and https are allowed.",
        )

    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid URL: missing hostname")

    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="URLs with embedded credentials are not allowed.")

    hostname = parsed.hostname.lower()

    if hostname in BLOCKED_HOSTNAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Access to '{hostname}' is not allowed.",
        )

    try:
        addr = socket.getaddrinfo(
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
        if not addr:
            raise HTTPException(status_code=400, detail=f"Could not resolve hostname: {hostname}")

        resolved_ips: set[str] = set()
        for entry in addr:
            ip_str = entry[4][0]
            if "%" in ip_str:
                ip_str = ip_str.split("%", 1)[0]
            resolved_ips.add(ip_str)

        for ip_str in resolved_ips:
            ip_addr = ipaddress.ip_address(ip_str)

            for network in BLOCKED_NETWORKS:
                if ip_addr in network:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Access to internal address '{ip_str}' is not allowed.",
                    )
    except HTTPException:
        raise
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"Could not resolve hostname: {hostname}")
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {url}")

    return url
