from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "username": username, "exp": expire, "type": "access"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "refresh"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(
        (User.username == username) | (User.email == username)
    ).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def get_user_permissions(db: Session, user_id: int) -> set[str]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return set()
    if user.is_superadmin:
        return {"*"}
    perms: set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            perms.add(perm.code)
    return perms


def ensure_default_admin(db: Session) -> None:
    """首次启动时创建超级管理员账号（若不存在）。"""
    if db.query(User).filter(User.is_superadmin == True).count() > 0:
        return
    admin = User(
        username="admin",
        email="admin@lawllm.local",
        hashed_password=hash_password("Admin@123456"),
        display_name="超级管理员",
        is_active=True,
        is_superadmin=True,
    )
    db.add(admin)
    db.commit()
