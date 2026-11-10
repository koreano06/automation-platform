import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models import AuthSession, User
from app.models.domain import utcnow
from app.schemas import LoginInput, SessionRead, UserInput, UserRead
from app.security import (
    COOKIE_NAME,
    admin_user,
    audit,
    create_user,
    current_user,
    token_hash,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def public_user(user):
    return {"id": user.id, "username": user.username, "role": user.role, "active": user.active}


@router.post("/login", response_model=SessionRead)
def login(payload: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    origin = request.headers.get("origin")
    if origin and origin not in settings.allowed_origins:
        raise HTTPException(403, "Origem não permitida.")
    user = db.scalar(select(User).where(User.username == payload.username.lower()))
    if user and user.locked_until and user.locked_until > utcnow():
        raise HTTPException(429, "Muitas tentativas. Aguarde cinco minutos.")
    valid = (
        verify_password(payload.password.get_secret_value(), user.password_hash)
        if user
        else verify_password(
            payload.password.get_secret_value(), "pbkdf2_sha256$600000$missing$invalid"
        )
    )
    if not user or not valid or not user.active:
        if user:
            user.login_attempts += 1
            if user.login_attempts >= 5:
                user.locked_until = utcnow() + timedelta(minutes=5)
            db.commit()
        raise HTTPException(401, "Usuário ou senha inválidos.")
    user.login_attempts = 0
    user.locked_until = None
    db.execute(delete(AuthSession).where(AuthSession.expires_at < utcnow()))
    token, csrf = secrets.token_urlsafe(32), secrets.token_hex(32)
    db.add(
        AuthSession(
            token_hash=token_hash(token),
            user_id=user.id,
            csrf_token=csrf,
            expires_at=utcnow() + timedelta(hours=settings.session_hours),
        )
    )
    audit(db, user, "auth.login", user.id)
    db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    return {"user": public_user(user), "csrf_token": csrf}


@router.get("/me", response_model=SessionRead)
def me(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = db.get(AuthSession, token_hash(request.cookies[COOKIE_NAME]))
    return {"user": public_user(user), "csrf_token": session.csrf_token}


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    db.execute(
        delete(AuthSession).where(
            AuthSession.token_hash == token_hash(request.cookies[COOKIE_NAME])
        )
    )
    audit(db, user, "auth.logout", user.id)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/users", response_model=list[UserRead])
def list_users(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [public_user(user) for user in db.scalars(select(User).order_by(User.username))]


@router.post("/users", status_code=201, response_model=UserRead)
def add_user(payload: UserInput, actor: User = Depends(admin_user), db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.username == payload.username.lower())):
        raise HTTPException(409, "Este usuário já existe.")
    user = create_user(db, payload.username, payload.password.get_secret_value(), payload.role)
    audit(db, actor, "user.created", user.id, role=user.role)
    db.commit()
    return public_user(user)


@router.post("/users/{user_id}/disable", response_model=UserRead)
def disable_user(user_id: str, actor: User = Depends(admin_user), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")
    if user.id == actor.id:
        raise HTTPException(409, "Não é permitido desativar a própria sessão.")
    user.active = False
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    audit(db, actor, "user.disabled", user.id)
    db.commit()
    return public_user(user)
