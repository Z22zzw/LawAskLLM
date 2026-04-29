import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, RefreshRequest, UserInfo
from app.services.auth_service import (
    authenticate_user, create_access_token, create_refresh_token,
    decode_token, hash_password,
)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, body.username, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    return TokenResponse(
        access_token=create_access_token(user.id, user.username),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/register", response_model=UserInfo, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter((User.username == body.username) | (User.email == body.email)).first():
        raise HTTPException(status_code=400, detail="用户名或邮箱已被使用")
    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name or body.username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token 无效")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return TokenResponse(
        access_token=create_access_token(user.id, user.username),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserInfo)
def me(current_user: User = Depends(get_current_user)):
    return current_user
