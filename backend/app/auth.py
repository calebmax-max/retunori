from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .core.config import get_settings
from .db import get_db
from .models import Role, Session, User

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)

def hash_password(value: str) -> str:
    return password_hash.hash(value)

def verify_password(value: str, hashed: str) -> bool:
    return password_hash.verify(value, hashed)

def create_token(user: User, db=None) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    sid = secrets.token_urlsafe(24)
    if db is not None:
        db.query(Session).filter(Session.user_id == user.id, Session.revoked_at.is_(None)).update({Session.revoked_at: datetime.utcnow()})
        db.add(Session(user_id=user.id, session_hash=hashlib.sha256(sid.encode()).hexdigest(), expires_at=expires.replace(tzinfo=None)))
        db.flush()
    payload = {"sub": str(user.id), "role": user.role.value, "sid": sid, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
        session = db.scalar(__import__('sqlalchemy').select(Session).where(Session.session_hash == hashlib.sha256(payload["sid"].encode()).hexdigest(), Session.user_id == user.id, Session.revoked_at.is_(None))) if user and payload.get("sid") else None
    except (jwt.PyJWTError, KeyError, ValueError):
        user = None; session = None
    if not user or not user.is_active or not session or session.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return user

def require_roles(*roles: Role):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return dependency

