"""Standard security response headers (branding + abuse-hardening ground rule).

CSP is intentionally permissive: it keeps existing inline scripts and styles
working while still being PRESENT (so clickjacking, MIME sniffing and mixed
content are constrained and HSTS is enforced). Tighten the CSP per app once the
page's real script/style/connect sources are known.
"""

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https:; "
        "frame-ancestors 'self'; base-uri 'self'; object-src 'none'"
    ),
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(self), camera=(self)",
}


def install(app):
    """Flask: attach the security headers to every response (does not clobber
    headers a view already set)."""
    @app.after_request
    def _set_security_headers(resp):
        for key, value in SECURITY_HEADERS.items():
            resp.headers.setdefault(key, value)
        return resp

    return app
