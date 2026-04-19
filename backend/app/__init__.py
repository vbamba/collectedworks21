# backend/app/__init__.py

import logging
import os
from datetime import datetime
from flask import Flask, request, abort, make_response
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# ───────────────────────────────────────────────────────────────────────
# Helpers to normalize host and scheme safely before Flask binds URLs
# ───────────────────────────────────────────────────────────────────────
def _clean_host(value: str) -> str:
    if not value:
        return ""
    v = value.strip().replace("\r", "").replace("\n", "")
    if "," in v:  # if proxies sent a list, take the first
        v = v.split(",", 1)[0].strip()
    v = v.strip(" '\"[]()")
    # strip port if present
    if ":" in v:
        host_part, port_part = v.rsplit(":", 1)
        if port_part.isdigit():
            v = host_part
    if not v or len(v) > 255:
        return ""
    for ch in v:
        if not (ch.isalnum() or ch in "-."):
            return ""
    if ".." in v or "/" in v:
        return ""
    return v

def _split_host_port(host: str, default_port: int) -> tuple[str, int]:
    # host may already be sans-port; infer port from scheme if missing
    if ":" in host:
        h, p = host.rsplit(":", 1)
        return (h, int(p)) if p.isdigit() else (host, default_port)
    return host, default_port

class HostHeadersSanitizer:
    """
    WSGI middleware:
      - sanitizes HTTP_HOST and X-Forwarded-Host
      - sets SERVER_NAME / SERVER_PORT / wsgi.url_scheme
      - removes invalid X-Forwarded-Host to avoid ProxyFix using garbage
    """
    def __init__(self, app, fallback_host: str, fallback_scheme: str = "https"):
        self.app = app
        self.fallback_host = fallback_host
        self.fallback_scheme = fallback_scheme

    def __call__(self, environ, start_response):
        # Resolve scheme first (prefer X-Forwarded-Proto)
        xf_proto = environ.get("HTTP_X_FORWARDED_PROTO", "").split(",")[0].strip()
        scheme = xf_proto if xf_proto in ("http", "https") else environ.get("wsgi.url_scheme", self.fallback_scheme)
        environ["wsgi.url_scheme"] = scheme

        # Clean X-Forwarded-Host
        xf_host_raw = environ.get("HTTP_X_FORWARDED_HOST", "")
        xf_host = _clean_host(xf_host_raw)
        if xf_host:
            environ["HTTP_X_FORWARDED_HOST"] = xf_host
        elif "HTTP_X_FORWARDED_HOST" in environ:
            environ.pop("HTTP_X_FORWARDED_HOST", None)

        # Clean HTTP_HOST (or fall back)
        raw_host = environ.get("HTTP_HOST", "")
        host = _clean_host(raw_host) or xf_host or self.fallback_host
        environ["HTTP_HOST"] = host

        # Critically, also set SERVER_NAME / SERVER_PORT so Map.bind() has sane values
        default_port = 443 if scheme == "https" else 80
        server_name, server_port = _split_host_port(host, default_port)
        environ["SERVER_NAME"] = server_name
        environ["SERVER_PORT"] = str(server_port)

        return self.app(environ, start_response)


def create_app():
    app = Flask(__name__)

    # Dev ergonomics
    app.config["DEBUG"] = True
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True

    # CORS (you can scope this to /api/* if you like)
    CORS(app, resources={r"/*": {"origins": "*"}})

    is_local = os.environ.get("FLASK_ENV") == "development" or os.environ.get("LOCAL_DEV") == "1"

    # Cache-busting version for templates
    build_version = os.environ.get("BUILD_VERSION") or datetime.utcnow().strftime("%Y%m%d%H%M%S")
    app.config["BUILD_VERSION"] = build_version

    @app.context_processor
    def inject_build_version():
        return {"build_version": app.config["BUILD_VERSION"]}

    fallback_host   = "localhost:5001" if is_local else "ask.collectedworksofsriaurobindo.com"
    fallback_scheme = "http" if is_local else "https"

    # NEW: prefer https in prod for url_for(..., _external=True)
    app.config['PREFERRED_URL_SCHEME'] = fallback_scheme

    # Sanitizer FIRST
    app.wsgi_app = HostHeadersSanitizer(app.wsgi_app, fallback_host, fallback_scheme)

    # ProxyFix ONCE (prod only)
    if not is_local and not getattr(app, "_proxyfix_applied", False):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
        app._proxyfix_applied = True

    # No-cache headers where needed
    @app.after_request
    def add_no_cache_headers(resp):
        nocache_prefixes = (
            "/api/search",
            "/api/text_search",
            "/api/chapter",
            "/api/chapter_content",
            "/api/filters",
            "/viewer",
        )
        try:
            if any(request.path.startswith(p) for p in nocache_prefixes):
                resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
                resp.headers["Pragma"] = "no-cache"
                resp.headers["Expires"] = "0"
        except Exception as e:
            app.logger.warning(f"Cache headers error for {getattr(request, 'path', '?')}: {e}")
        return resp

    # Logging (no duplicate handlers in Gunicorn)
    logger = logging.getLogger(__name__)
    logger.propagate = False
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.StreamHandler())
        logger.addHandler(logging.FileHandler("search.log"))

    # ─────────────────────────────────────────────────────────────
    # CHANGED: Guard /api/filters only in PROD. In local/dev we skip.
    # Also make the allow-list host-only (no port), since _clean_host()
    # strips the port. This fixes your 400s with Host='127.0.0.1'.
    # ─────────────────────────────────────────────────────────────
    @app.before_request
    def _guard_filters_host():
        if request.path != "/api/filters":
            return
        # Skip the guard entirely when running locally
        if is_local:
            return
        # In prod, enforce expected hostnames (no port)
        host_clean = _clean_host(request.headers.get("Host", ""))
        allowed_hosts = {
            "ask.collectedworksofsriaurobindo.com",  # prod
            # keep localhost/127.0.0.1 here only if you ever test prod behind SSH tunnels
            # "localhost",
            # "127.0.0.1",
        }
        if host_clean not in allowed_hosts:
            app.logger.warning(f"[FiltersHostGuard] Rejecting Host='{request.headers.get('Host','')}' on /api/filters")
            abort(400)

    # Fast OPTIONS handler for /api/filters (preflight short-circuit)
    @app.route("/api/filters", methods=["OPTIONS"])
    def _filters_options():
        resp = make_response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = request.headers.get("Access-Control-Request-Headers", "Content-Type")
        resp.headers["Vary"] = "Origin"
        return resp

    # EXTRA: Quick visibility if anything still looks odd
    @app.before_request
    def _log_if_suspicious_host():
        host = request.headers.get("Host", "")
        xf_host = request.headers.get("X-Forwarded-Host", "")
        # Log only when suspicious (so logs stay clean)
        if not _clean_host(host) or (xf_host and not _clean_host(xf_host)):
            app.logger.warning(
                f"[HostSanity] Suspicious headers. "
                f"Host='{host}' X-Forwarded-Host='{xf_host}' "
                f"Path='{request.path}'"
            )

    # Routes
    with app.app_context():
        from .routes import main
        app.register_blueprint(main)

    return app
