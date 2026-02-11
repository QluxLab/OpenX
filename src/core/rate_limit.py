"""
Secure rate limiting utilities for OpenX application.

Provides a secure key function for rate limiting that properly handles
X-Forwarded-For headers by only trusting them from known proxy IPs.
"""
import os
from typing import Callable

from fastapi import Request


def parse_trusted_proxies() -> set[str]:
    """
    Parse trusted proxy IPs from environment variable.

    The OPENX_TRUSTED_PROXIES environment variable should contain a
    comma-separated list of IP addresses that are trusted to send
    legitimate X-Forwarded-For headers.

    Example: OPENX_TRUSTED_PROXIES="10.0.0.1,10.0.0.2,172.16.0.0/12"

    Supports both individual IPs and CIDR notation.

    Returns:
        Set of trusted IP addresses (expanded if CIDR ranges provided).
    """
    proxy_config = os.getenv("OPENX_TRUSTED_PROXIES", "")

    if not proxy_config:
        return set()

    trusted = set()
    for proxy in proxy_config.split(","):
        proxy = proxy.strip()
        if not proxy:
            continue

        # Handle CIDR notation
        if "/" in proxy:
            try:
                import ipaddress
                network = ipaddress.ip_network(proxy, strict=False)
                trusted.update(str(ip) for ip in network.hosts())
            except ValueError:
                # Invalid CIDR, skip
                continue
        else:
            trusted.add(proxy)

    return trusted


# Cache the trusted proxies at module level to avoid re-parsing on every request
_TRUSTED_PROXIES: set[str] | None = None


def get_trusted_proxies() -> set[str]:
    """Get cached trusted proxies, parsing on first access."""
    global _TRUSTED_PROXIES
    if _TRUSTED_PROXIES is None:
        _TRUSTED_PROXIES = parse_trusted_proxies()
    return _TRUSTED_PROXIES


def get_real_client_ip(request: Request) -> str:
    """
    Get the real client IP address for rate limiting.

    This function implements a secure approach to handling X-Forwarded-For
    headers by only trusting them when the direct client IP is in the
    trusted proxies list.

    Security rationale:
    - Direct clients can spoof X-Forwarded-For to bypass rate limits
    - Only proxies we control should be trusted to set this header
    - When behind a trusted proxy, we use the rightmost non-trusted IP
      from X-Forwarded-For (the original client)

    Args:
        request: The FastAPI request object.

    Returns:
        The client IP address to use for rate limiting.
    """
    # Get the direct client IP (the immediate TCP connection)
    direct_client_ip = request.client.host if request.client else "unknown"

    # Get trusted proxies
    trusted_proxies = get_trusted_proxies()

    # If no trusted proxies configured, just use direct client IP
    if not trusted_proxies:
        return direct_client_ip

    # Only trust X-Forwarded-For if the direct client is a trusted proxy
    if direct_client_ip not in trusted_proxies:
        return direct_client_ip

    # We're behind a trusted proxy, so extract the real client IP from X-Forwarded-For
    x_forwarded_for = request.headers.get("X-Forwarded-For")

    if not x_forwarded_for:
        # No X-Forwarded-For header, use direct client
        return direct_client_ip

    # X-Forwarded-For format: client, proxy1, proxy2, ...
    # The leftmost value is the original client, rightmost is the most recent proxy
    # We want the rightmost non-trusted IP (the client that connected to our first proxy)
    ips = [ip.strip() for ip in x_forwarded_for.split(",")]

    # Find the rightmost IP that is NOT a trusted proxy
    for ip in reversed(ips):
        if ip and ip not in trusted_proxies:
            return ip

    # All IPs in chain are trusted proxies, use the leftmost (original source)
    return ips[0] if ips else direct_client_ip


def get_real_client_ip_factory() -> Callable[[Request], str]:
    """
    Factory function that returns the get_real_client_ip function.

    This is useful for slowapi which expects a callable that takes a Request.
    Direct use of get_real_client_ip also works since it matches the expected signature.

    Returns:
        The get_real_client_ip function.
    """
    return get_real_client_ip
