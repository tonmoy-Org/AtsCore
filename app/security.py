import os
import hmac
import logging
from flask import request, jsonify, g
from app.config import Config

logger = logging.getLogger("atscore.security")


def extract_api_key() -> str:
    """
    Extracts authentication key from multiple possible request vectors:
    1. Header: Authorization: Bearer <hex_key> or Authorization: <hex_key>
    2. Header: X-API-Key / X-Secret-Key / X-Auth-Token
    3. Query parameter: ?api_key=... or ?token=... or ?secret=...
    4. JSON Body: {"api_key": "..."} or {"token": "..."}
    5. Form data: api_key=... or token=...
    """
    # 1. Authorization header
    auth_hdr = request.headers.get("Authorization", "")
    if auth_hdr:
        if auth_hdr.lower().startswith("bearer "):
            return auth_hdr[7:].strip()
        if not auth_hdr.lower().startswith("basic "):
            return auth_hdr.strip()

    # 2. Custom API key headers
    for hdr in ("X-API-Key", "X-Secret-Key", "X-Auth-Token"):
        val = request.headers.get(hdr)
        if val:
            return val.strip()

    # 3. Query string parameters
    for param in ("api_key", "token", "secret", "auth"):
        val = request.args.get(param)
        if val:
            return val.strip()

    # 4. JSON body
    if request.is_json:
        data = request.get_json(silent=True) or {}
        for key in ("api_key", "token", "secret", "auth"):
            if key in data:
                return str(data[key]).strip()

    # 5. Form data
    if request.form:
        for key in ("api_key", "token", "secret", "auth"):
            if key in request.form:
                return request.form.get(key, "").strip()

    return None


def verify_api_key(provided_key: str) -> bool:
    """
    Constant-time comparison against Config.SECRET_KEY to prevent timing attacks.
    """
    secret = Config.SECRET_KEY
    if not secret or not provided_key:
        return False
    return hmac.compare_digest(str(provided_key).strip(), str(secret).strip())


def authenticate_request():
    """
    Before-request security barrier.
    Protects all routes while permitting CORS preflights.
    """
    # Always allow CORS preflight requests
    if request.method == "OPTIONS":
        return None

    # Check if public health check is explicitly allowed via env
    allow_public_health = os.getenv("ALLOW_PUBLIC_HEALTH", "0") in ("1", "true", "True")
    if allow_public_health and request.path == "/health":
        return None

    key = extract_api_key()
    if not key or not verify_api_key(key):
        logger.warning(
            f"Unauthorized request blocked: {request.method} {request.path} from {request.remote_addr}"
        )
        return jsonify({
            "ok": False,
            "error": "Unauthorized: Invalid or missing API key. Provide SECRET_KEY via Authorization Bearer, X-API-Key, or ?api_key="
        }), 401

    g.authenticated = True
    return None


def add_security_headers(response):
    """Adds enterprise security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

