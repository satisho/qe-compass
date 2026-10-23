"""Password hashing and session tokens (standard library only).

Passwords use scrypt with a per-password salt. Sessions are random tokens held
in an HttpOnly cookie; only a SHA-256 hash of each token is stored, so a copy
of the database cannot be used to hijack sessions.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_N, _R, _P, _LEN = 2**14, 8, 1, 64


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_LEN)
    return "scrypt${}${}${}${}${}".format(
        _N, _R, _P, base64.b64encode(salt).decode(), base64.b64encode(dk).decode()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, dk_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(dk_b64)
        dk = hashlib.scrypt(password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def password_problem(password: str) -> str | None:
    if len(password) < 10:
        return "Use at least 10 characters."
    if password.lower() == password or password.upper() == password or not any(c.isdigit() for c in password):
        return "Mix upper- and lower-case letters and include a number."
    return None


# ---- two-step verification: time-based one-time passwords (RFC 6238) ------
import struct
import time as _time

TOTP_PERIOD, TOTP_DIGITS = 30, 6


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 10**TOTP_DIGITS
    return str(code).zfill(TOTP_DIGITS)


def totp_now(secret: str, at: float | None = None) -> str:
    return _hotp(secret, int((at if at is not None else _time.time()) // TOTP_PERIOD))


def verify_totp(secret: str, code: str, last_step: int | None = None, at: float | None = None) -> int | None:
    """Return the matched time step (so callers can block reuse), or None.

    Accepts one step of clock drift either way, and never a step at or before `last_step`.
    """
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != TOTP_DIGITS:
        return None
    now = int((at if at is not None else _time.time()) // TOTP_PERIOD)
    for step in (now - 1, now, now + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(_hotp(secret, step), code):
            return step
    return None


def totp_uri(secret: str, email: str, issuer: str = "QE Compass") -> str:
    from urllib.parse import quote

    return (f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}"
            f"&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD}")
