"""Security headers for every HTTP response."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if not request.url.path.startswith(_DOC_PATHS):
            headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
        if request.url.path.startswith("/api/"):
            headers.setdefault("Cache-Control", "no-store")
        return response
