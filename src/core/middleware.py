"""
Security middleware for OpenX application
Handles CSRF protection, security headers, and cookie security
"""
import secrets
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


# Security headers configuration
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # CSP allows inline scripts for simplicity but restricts external sources
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Add security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value

        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware.

    For GET requests: Generate and attach a CSRF token
    For POST/PUT/PATCH/DELETE requests: Validate the CSRF token

    API routes are exempt since they use X-Secret-Key header authentication.
    """

    CSRF_HEADER = "X-CSRF-Token"
    CSRF_COOKIE = "csrf_token"
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

    def _is_api_route(self, path: str) -> bool:
        """Check if the path is an API route (exempt from CSRF)."""
        return path.startswith("/api/")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate CSRF token for session
        csrf_token = request.cookies.get(self.CSRF_COOKIE)

        if not csrf_token:
            csrf_token = secrets.token_urlsafe(32)

        # For safe methods, just proceed
        if request.method in self.SAFE_METHODS:
            response = await call_next(request)
            # Set CSRF cookie if not present
            if not request.cookies.get(self.CSRF_COOKIE):
                response.set_cookie(
                    key=self.CSRF_COOKIE,
                    value=csrf_token,
                    httponly=False,  # Must be accessible to JS
                    secure=False,  # Set True in production with HTTPS
                    samesite="strict",
                    max_age=60 * 60 * 24 * 365,  # 1 year
                )
            return response

        # For unsafe methods, validate CSRF token
        # API routes are exempt (they use X-Secret-Key header auth)
        if self._is_api_route(request.url.path):
            return await call_next(request)

        # Check for CSRF token in header
        header_token = request.headers.get(self.CSRF_HEADER)
        cookie_token = request.cookies.get(self.CSRF_COOKIE)

        if not header_token or not cookie_token:
            return JSONResponse(
                {"detail": "CSRF token missing"},
                status_code=403,
            )

        if not secrets.compare_digest(header_token, cookie_token):
            return JSONResponse(
                {"detail": "Invalid CSRF token"},
                status_code=403,
            )

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log requests for audit purposes"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Import logger here to avoid circular imports
        from src.core.logger import get_logger

        logger = get_logger("requests")

        # Log the request
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f"{request.method} {request.url.path} - IP: {client_ip}")

        response = await call_next(request)

        # Log the response status
        logger.info(f"{request.method} {request.url.path} - Status: {response.status_code}")

        return response
