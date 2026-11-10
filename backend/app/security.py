import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import AuditEvent, AuthSession, User
from app.models.domain import utcnow

COOKIE_NAME = "automation_session"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return f"pbkdf2_sha256$600000${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME, "")
    session = db.get(AuthSession, token_hash(token)) if token else None
    if not session or session.expires_at <= utcnow() or not session.user.active:
        raise HTTPException(status_code=401, detail="Sessão ausente ou expirada.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(csrf, session.csrf_token):
            raise HTTPException(status_code=403, detail="Token de proteção inválido.")
    return session.user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Esta operação exige um administrador.")
    return user


def audit(db: Session, actor: User | None, action: str, resource_id: str, **details):
    db.add(
        AuditEvent(
            actor_id=actor.id if actor else None,
            action=action,
            resource_id=resource_id,
            details=details,
        )
    )


def create_user(db: Session, username: str, password: str, role: str) -> User:
    if len(password) < 12:
        raise ValueError("A senha deve ter pelo menos 12 caracteres.")
    user = User(username=username.lower().strip(), password_hash=hash_password(password), role=role)
    db.add(user)
    db.flush()
    return user
