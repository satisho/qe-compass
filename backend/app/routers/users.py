from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, require_admin
from ..models import User, UserSession
from ..schemas import ResetPasswordIn, UserCreate, UserUpdate, user_out
from ..security import hash_password, password_problem

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/directory")
def directory(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict]:
    """Names only, so the UI can attribute changes."""
    return [{"id": u.id, "name": u.name} for u in db.scalars(select(User))]


@router.get("")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[dict]:
    return [user_out(u) for u in db.scalars(select(User).order_by(User.name))]


@router.post("", status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict:
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")
    if problem := password_problem(body.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)
    u = User(email=email, name=body.name, role=body.role, password_hash=hash_password(body.password),
             must_change_password=True)
    db.add(u)
    db.commit()
    return user_out(u)


def _admins_left(db: Session, excluding: int) -> int:
    return db.scalar(select(func.count(User.id)).where(User.role == "admin", User.active.is_(True), User.id != excluding)) or 0


@router.patch("/{uid}")
def update_user(uid: int, body: UserUpdate, db: Session = Depends(get_db), me: User = Depends(require_admin)) -> dict:
    u = db.get(User, uid)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    demoting = (body.role and body.role != "admin") or body.active is False
    if u.role == "admin" and demoting and _admins_left(db, u.id) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Keep at least one active administrator.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(u, k, v)
    if body.active is False:
        db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    db.commit()
    return user_out(u)


@router.post("/{uid}/reset-password")
def reset_password(uid: int, body: ResetPasswordIn, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict:
    u = db.get(User, uid)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    if problem := password_problem(body.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)
    u.password_hash = hash_password(body.password)
    u.must_change_password = True
    db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    db.commit()
    return {"ok": True}
