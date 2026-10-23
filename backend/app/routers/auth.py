from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import audit
from ..config import settings
from ..db import get_db
from ..deps import COOKIE_NAME, current_user, session_for
from ..models import User, UserSession
from ..schemas import ChangePasswordIn, LoginIn, MfaCodeIn, MfaDisableIn, SetupIn, user_out
from ..security import (hash_password, new_token, new_totp_secret, password_problem, token_hash, totp_uri,
                        verify_password, verify_totp)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Failed sign-ins are counted from the security log, so limits survive restarts and
# apply across processes: 5 per account and 20 per network address per 15 minutes.
MAX_FAILS_PER_ACCOUNT, MAX_FAILS_PER_IP, WINDOW_MINUTES = 5, 20, 15


def _secure(request: Request) -> bool:
    return settings.cookie_secure or request.url.scheme == "https"


def _start_session(db: Session, user: User, request: Request, response: Response) -> None:
    token = new_token()
    now = datetime.now(timezone.utc)
    db.add(UserSession(user_id=user.id, token_hash=token_hash(token), expires_at=now + timedelta(hours=settings.session_hours),
                       last_seen_at=now))
    db.execute(delete(UserSession).where(UserSession.expires_at < now))
    user.last_login_at = now
    audit.record(db, "login_success", request, user=user)
    db.commit()
    response.set_cookie(
        COOKIE_NAME, token, max_age=settings.session_hours * 3600, httponly=True,
        samesite="strict", secure=_secure(request), path="/",
    )


def _policy() -> dict:
    return {"require_mfa": settings.require_mfa, "idle_minutes": settings.idle_minutes}


@router.get("/status")
def setup_status(db: Session = Depends(get_db)) -> dict:
    return {"needs_setup": (db.scalar(select(func.count(User.id))) or 0) == 0}


@router.post("/setup")
def first_admin(body: SetupIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    if (db.scalar(select(func.count(User.id))) or 0) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Setup is already complete. Sign in instead.")
    if problem := password_problem(body.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    user = User(email=body.email.lower(), name=body.name, password_hash=hash_password(body.password), role="admin")
    db.add(user)
    db.flush()
    audit.record(db, "setup_admin", request, user=user)
    _start_session(db, user, request, response)
    return user_out(user)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    email, ip = body.email.lower(), audit.client_ip(request)
    if (audit.recent_failures(db, email=email, minutes=WINDOW_MINUTES) >= MAX_FAILS_PER_ACCOUNT
            or (ip and audit.recent_failures(db, ip=ip, minutes=WINDOW_MINUTES) >= MAX_FAILS_PER_IP)):
        audit.record_now(db, "login_blocked", request, email=email)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Wait 15 minutes and try again.")
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(body.password, user.password_hash):
        audit.record_now(db, "login_failed", request, user=user, email=email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    if not user.active:
        audit.record_now(db, "login_failed", request, user=user, detail="account deactivated")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is deactivated. Ask an administrator.")
    if user.mfa_enabled and user.mfa_secret:
        if not body.code:
            return {"mfa_required": True}
        step = verify_totp(user.mfa_secret, body.code, user.mfa_last_step)
        if step is None:
            audit.record_now(db, "mfa_failed", request, user=user)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That code didn't work. Check your authenticator app and try again.")
        user.mfa_last_step = step
    _start_session(db, user, request, response)
    return {**user_out(user), **_policy()}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        sess = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(token)))
        if sess:
            audit.record(db, "logout", request, user=sess.user)
            db.delete(sess)
            db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/session")
def session(request: Request, db: Session = Depends(get_db)) -> dict:
    """Like /me, but answers 200 with user=null when signed out (avoids noisy 401s on page load)."""
    try:
        return {"user": user_out(session_for(request, db).user), **_policy()}
    except HTTPException:
        return {"user": None, **_policy()}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return user_out(user)


@router.post("/change-password")
def change_password(body: ChangePasswordIn, request: Request, user: User = Depends(current_user),
                    db: Session = Depends(get_db)) -> dict:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your current password is incorrect.")
    if problem := password_problem(body.new_password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    user = db.merge(user)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    # sign out other sessions
    current = token_hash(request.cookies.get(COOKIE_NAME, ""))
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.token_hash != current))
    audit.record(db, "password_changed", request, user=user)
    db.commit()
    return {"ok": True}


# ---- two-step verification ---------------------------------------------------
@router.post("/mfa/setup")
def mfa_setup(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Start setup: a new secret to scan. It only takes effect once a code is confirmed."""
    import io

    import segno

    if user.mfa_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Two-step verification is already on.")
    user = db.merge(user)
    user.mfa_secret = new_totp_secret()
    db.commit()
    uri = totp_uri(user.mfa_secret, user.email)
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=5, border=2, dark="#0b2a55", xmldecl=False)
    return {"secret": user.mfa_secret, "uri": uri,
            "qr_svg": "data:image/svg+xml;base64," + __import__("base64").b64encode(buf.getvalue()).decode()}


@router.post("/mfa/enable")
def mfa_enable(body: MfaCodeIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    user = db.merge(user)
    if not user.mfa_secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Start setup first.")
    step = verify_totp(user.mfa_secret, body.code)
    if step is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code didn't match. Check the time on your phone and try the next code.")
    user.mfa_enabled, user.mfa_last_step = True, step
    audit.record(db, "mfa_enabled", request, user=user)
    db.commit()
    return user_out(user)


@router.post("/mfa/disable")
def mfa_disable(body: MfaDisableIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if settings.require_mfa:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Two-step verification is required for everyone on this installation.")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your password is incorrect.")
    user = db.merge(user)
    user.mfa_enabled, user.mfa_secret, user.mfa_last_step = False, None, None
    audit.record(db, "mfa_disabled", request, user=user)
    db.commit()
    return user_out(user)
