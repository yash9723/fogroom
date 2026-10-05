"""Security headers for every HTTP response."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")
_API_PATHS = ("/api/", "/health", "/ws/")
# Static Next.js export: inline bootstrap scripts/styles, same-origin API + WebSocket.
_PAGE_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        path = request.url.path
        if path.startswith(_API_PATHS):
            headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
        elif not path.startswith(_DOC_PATHS):
            headers.setdefault("Content-Security-Policy", _PAGE_CSP)
        if request.url.path.startswith("/api/"):
            headers.setdefault("Cache-Control", "no-store")
        return response
