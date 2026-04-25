from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    display_name: str = ""
    is_superadmin: bool = False
    role_ids: list[int] = []


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None
    is_active: bool | None = None
    password: str | None = None
    role_ids: list[int] | None = None


class RoleOut(BaseModel):
    id: int
    name: str
    description: str
    is_system: bool

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    display_name: str
    is_active: bool
    is_superadmin: bool
    roles: list[RoleOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    name: str
    description: str = ""
    permission_codes: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_codes: list[str] | None = None


class PermissionOut(BaseModel):
    id: int
    code: str
    description: str

    class Config:
        from_attributes = True
