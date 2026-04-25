from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_superadmin
from app.models.user import User, Role, Permission
from app.schemas.user import UserCreate, UserUpdate, UserOut, RoleCreate, RoleUpdate, RoleOut, PermissionOut
from app.services.auth_service import hash_password, ensure_default_admin

router = APIRouter(tags=["用户与权限"])


# ── 用户管理 ──

@router.get("/users", response_model=list[UserOut])
def list_users(
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    return db.query(User).offset(skip).limit(limit).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    if db.query(User).filter((User.username == body.username) | (User.email == body.email)).first():
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")
    roles = db.query(Role).filter(Role.id.in_(body.role_ids)).all() if body.role_ids else []
    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name or body.username,
        is_superadmin=body.is_superadmin,
        roles=roles,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, body: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.email is not None:
        user.email = body.email
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password:
        user.hashed_password = hash_password(body.password)
    if body.role_ids is not None:
        user.roles = db.query(Role).filter(Role.id.in_(body.role_ids)).all()
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), current: User = Depends(require_superadmin)):
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()


# ── 角色管理 ──

@router.get("/roles", response_model=list[RoleOut])
def list_roles(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Role).all()


@router.post("/roles", response_model=RoleOut, status_code=201)
def create_role(body: RoleCreate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    role = Role(name=body.name, description=body.description)
    if body.permission_codes:
        role.permissions = db.query(Permission).filter(Permission.code.in_(body.permission_codes)).all()
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(role_id: int, body: RoleUpdate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统内置角色不可修改")
    if body.name is not None:
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    if body.permission_codes is not None:
        role.permissions = db.query(Permission).filter(Permission.code.in_(body.permission_codes)).all()
    db.commit()
    db.refresh(role)
    return role


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Permission).all()
