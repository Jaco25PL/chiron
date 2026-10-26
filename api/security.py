"""Who is calling the backend.

The browser never talks to the backend directly: the Next.js server (web/app/api/[...path])
checks the Google session and forwards the request with the user's identity, signed with a
shared secret (CHIRON_BACKEND_SECRET):

    x-chiron-user: student email
    x-chiron-name: display name, URL-encoded
    x-chiron-ts:   unix seconds
    x-chiron-sig:  hex HMAC-SHA256(secret, f"{email}\\n{name}\\n{ts}")

Without CHIRON_BACKEND_SECRET (local development) requests are accepted and the user comes
from x-chiron-user, defaulting to a dev user. In a deployment the secret must be set.
"""

import hashlib
import hmac
import os
import time
from urllib.parse import unquote

MAX_SKEW_S = 300
DEV_USER = {"email": "dev@localhost", "name": "Dev"}


class Unauthorized(Exception):
    pass


def sign(secret: str, email: str, name: str, ts: str) -> str:
    return hmac.new(secret.encode(), f"{email}\n{name}\n{ts}".encode(), hashlib.sha256).hexdigest()


def verify(headers, secret: str | None = None, now: float | None = None) -> dict:
    """Returns {"email", "name"} or raises Unauthorized. `headers` is any case-insensitive mapping."""
    secret = os.environ.get("CHIRON_BACKEND_SECRET") if secret is None else secret
    if not secret and os.environ.get("VERCEL"):
        # deployed without the secret: refuse everything instead of trusting unsigned headers
        raise Unauthorized("backend secret not configured")
    email = headers.get("x-chiron-user")
    raw_name = headers.get("x-chiron-name") or ""  # signed as sent (URL-encoded)
    name = unquote(raw_name)
    if not secret:  # dev mode
        return {"email": email, "name": name or None} if email else DEV_USER
    ts, sig = headers.get("x-chiron-ts"), headers.get("x-chiron-sig")
    if not (email and ts and sig):
        raise Unauthorized("missing identity headers")
    try:
        age = abs((now or time.time()) - int(ts))
    except ValueError:
        raise Unauthorized("bad timestamp")
    if age > MAX_SKEW_S:
        raise Unauthorized("expired signature")
    if not hmac.compare_digest(sign(secret, email, raw_name, ts), sig):
        raise Unauthorized("bad signature")
    return {"email": email, "name": name or None}
