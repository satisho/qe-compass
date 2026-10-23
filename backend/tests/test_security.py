"""Security controls added in 1.0.1 (findings F-02 to F-10 of the v1.0 security review)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import SecurityEvent, UserSession
from app.security import totp_now, verify_totp

from .conftest import Client


def _new_user(admin: Client, email: str, role: str = "assessor", pw: str = "Passw0rdLong") -> int:
    return admin.post("/api/users", json={"name": email.split("@")[0], "email": email, "role": role, "password": pw},
                      expect=201).json()["id"]


def _events(admin: Client, kind: str) -> list[dict]:
    return admin.get(f"/api/security-events?kind={kind}").json()


def test_totp_rfc6238_vector():
    # RFC 6238 appendix B, SHA-1, T=59 -> 94287082 (8 digits); our 6-digit code is its last 6 digits
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # base32 of "12345678901234567890"
    assert totp_now(secret, at=59) == "287082"
    assert verify_totp(secret, "287082", at=59) == 1
    assert verify_totp(secret, "287082", last_step=1, at=59) is None  # replay blocked


def test_two_step_verification(admin):
    _new_user(admin, "mfa@example.com")
    with TestClient(app) as t:
        u = Client(t)
        u.post("/api/auth/login", json={"email": "mfa@example.com", "password": "Passw0rdLong"}, expect=200)
        setup = u.post("/api/auth/mfa/setup", expect=200).json()
        assert setup["uri"].startswith("otpauth://totp/") and setup["qr_svg"].startswith("data:image/svg+xml;base64,")
        assert u.post("/api/auth/mfa/enable", json={"code": "000000"}).status_code == 400
        u.post("/api/auth/mfa/enable", json={"code": totp_now(setup["secret"])}, expect=200)
        u.post("/api/auth/logout", expect=200)
        # password alone is no longer enough
        r = u.post("/api/auth/login", json={"email": "mfa@example.com", "password": "Passw0rdLong"}, expect=200).json()
        assert r == {"mfa_required": True}
        assert u.get("/api/auth/me", expect=None).status_code == 401
        assert u.post("/api/auth/login", json={"email": "mfa@example.com", "password": "Passw0rdLong", "code": "123456"}).status_code == 401
        # the code used to enable can't be replayed; the next step's code works
        nxt = totp_now(setup["secret"], at=datetime.now().timestamp() + 30)
        u.post("/api/auth/login", json={"email": "mfa@example.com", "password": "Passw0rdLong", "code": nxt}, expect=200)
        assert u.get("/api/auth/me").json()["mfa_enabled"] is True
    assert _events(admin, "mfa_enabled") and _events(admin, "mfa_failed")
    # admin can reset a lost authenticator
    uid = next(x["id"] for x in admin.get("/api/users").json() if x["email"] == "mfa@example.com")
    assert admin.post(f"/api/users/{uid}/reset-mfa", expect=200).json()["mfa_enabled"] is False


def test_require_mfa_blocks_until_set_up(admin, engagement):
    _new_user(admin, "must@example.com")
    object.__setattr__(settings, "require_mfa", True)
    try:
        with TestClient(app) as t:
            u = Client(t)
            body = u.post("/api/auth/login", json={"email": "must@example.com", "password": "Passw0rdLong"}, expect=200).json()
            assert body["require_mfa"] is True and body["mfa_enabled"] is False
            assert u.get("/api/engagements", expect=None).status_code == 403
            s = u.post("/api/auth/mfa/setup", expect=200).json()
            u.post("/api/auth/mfa/enable", json={"code": totp_now(s["secret"])}, expect=200)
            u.get("/api/engagements", expect=200)
            assert u.post("/api/auth/mfa/disable", json={"password": "Passw0rdLong"}).status_code == 400
    finally:
        object.__setattr__(settings, "require_mfa", False)


def test_sign_in_throttle_is_persistent(admin):
    _new_user(admin, "throttle@example.com")
    with TestClient(app) as t:
        u = Client(t)
        for _ in range(5):
            assert u.post("/api/auth/login", json={"email": "throttle@example.com", "password": "wrong"}).status_code == 401
        assert u.post("/api/auth/login", json={"email": "throttle@example.com", "password": "Passw0rdLong"}).status_code == 429
    # stored in the database, so a restart (new client, fresh process state) doesn't clear it
    with TestClient(app) as t:
        assert Client(t).post("/api/auth/login", json={"email": "throttle@example.com", "password": "Passw0rdLong"}).status_code == 429
    assert _events(admin, "login_blocked")
    # once the window passes, sign-in works and earlier failures stop counting
    with SessionLocal() as db:
        db.execute(update(SecurityEvent).where(SecurityEvent.email == "throttle@example.com")
                   .values(created_at=datetime.now(timezone.utc) - timedelta(minutes=20)))
        db.commit()
    with TestClient(app) as t:
        Client(t).post("/api/auth/login", json={"email": "throttle@example.com", "password": "Passw0rdLong"}, expect=200)


def test_security_log_is_admin_only_and_records_admin_actions(admin):
    uid = _new_user(admin, "audited@example.com", role="viewer")
    admin.patch(f"/api/users/{uid}", json={"role": "assessor"})
    admin.post(f"/api/users/{uid}/reset-password", json={"password": "Another1Pass"}, expect=200)
    kinds = {e["kind"] for e in admin.get("/api/security-events").json()}
    assert {"user_created", "user_updated", "password_reset", "login_success"} <= kinds
    upd = _events(admin, "user_updated")[0]
    assert "role: viewer -> assessor" in upd["detail"] and upd["label"] == "User changed"
    with TestClient(app) as t:
        u = Client(t)
        u.post("/api/auth/login", json={"email": "audited@example.com", "password": "Another1Pass"}, expect=200)
        assert u.get("/api/security-events", expect=None).status_code == 403


def test_idle_timeout(admin):
    _new_user(admin, "idle@example.com")
    with TestClient(app) as t:
        u = Client(t)
        u.post("/api/auth/login", json={"email": "idle@example.com", "password": "Passw0rdLong"}, expect=200)
        u.get("/api/auth/me")
        with SessionLocal() as db:
            db.execute(update(UserSession).values(last_seen_at=datetime.now(timezone.utc) - timedelta(minutes=settings.idle_minutes + 1))
                       .where(UserSession.user_id == u.get("/api/auth/me").json()["id"]))
            db.commit()
        r = u.get("/api/auth/me", expect=None)
        assert r.status_code == 401 and "inactivity" in r.json()["detail"]
    assert _events(admin, "session_idle")


def test_engagement_access(admin, engagement):
    eid = engagement["id"]
    uid = _new_user(admin, "outsider@example.com")
    with TestClient(app) as t:
        u = Client(t)
        u.post("/api/auth/login", json={"email": "outsider@example.com", "password": "Passw0rdLong"}, expect=200)
        for path in (f"/api/engagements/{eid}", f"/api/engagements/{eid}/workspace", f"/api/engagements/{eid}/evidence",
                     f"/api/engagements/{eid}/export.json", f"/api/engagements/{eid}/members"):
            assert u.get(path, expect=None).status_code == 404, path
        assert u.post(f"/api/engagements/{eid}/entities", json={"name": "X"}).status_code == 404
        # an assessor's own engagement is visible to them without membership
        own = u.post("/api/engagements", json={"client": "B", "title": "Own", "start_date": "2026-10-01"}, expect=201).json()
        u.get(f"/api/engagements/{own['id']}/workspace")
        admin.post(f"/api/engagements/{eid}/members", json={"user_id": uid}, expect=201)
        u.get(f"/api/engagements/{eid}/workspace")
        admin.delete(f"/api/engagements/{eid}/members/{uid}")
        assert u.get(f"/api/engagements/{eid}/workspace", expect=None).status_code == 404
    assert _events(admin, "member_added") and _events(admin, "member_removed")


def test_uploads_links_exports(admin, engagement):
    eid = engagement["id"]
    for bad in ("tool.exe", "page.html", "macro.xlsm", "image.svg", "archive.zip"):
        r = admin.post(f"/api/engagements/{eid}/evidence/upload", files={"files": (bad, b"x")})
        assert r.status_code == 400, bad
    ok = admin.post(f"/api/engagements/{eid}/evidence/upload", files={"files": ("strategy.txt", b"Test strategy", "text/html")},
                    expect=201).json()[0]
    f = admin.get(f"/api/engagements/{eid}/evidence/{ok['id']}/file")
    assert f.headers["content-type"].startswith("text/plain")  # type comes from the extension, not the browser
    assert "attachment" in f.headers["content-disposition"]
    for url in ("javascript:alert(1)", "data:text/html,x", "file:///etc/passwd"):
        assert admin.post(f"/api/engagements/{eid}/evidence/link", json={"name": "L", "url": url}).status_code == 422
    admin.post(f"/api/engagements/{eid}/evidence/link", json={"name": "L", "url": "https://confluence.example/x"}, expect=201)
    admin.get(f"/api/engagements/{eid}/export.csv")
    assert any(f"#{eid}" in e["detail"] for e in _events(admin, "data_export"))


def test_headers_and_api_docs(admin):
    assert admin.get("/api/docs", expect=None).status_code == 404
    assert admin.get("/api/openapi.json", expect=None).status_code == 404
    r = admin.get("/api/health")
    assert r.json()["version"] == "1.0.1"
    for h in ("content-security-policy", "x-frame-options", "x-content-type-options", "referrer-policy", "permissions-policy"):
        assert h in r.headers
