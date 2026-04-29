from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database import engine, SessionLocal
from app.models import *  # noqa: F401, F403 — 确保所有模型在 create_all 前导入
from app.database import Base
from app.api import auth, users, chat, knowledge, dataset_vector, experiments
from app.services.auth_service import ensure_default_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_admin(db)
        _seed_permissions(db)
    finally:
        db.close()
    yield


def _seed_permissions(db):
    from app.models.user import Permission
    default_perms = [
        ("kb:read",    "查看知识库"),
        ("kb:write",   "创建/编辑知识库"),
        ("kb:delete",  "删除知识库"),
        ("chat:use",   "使用对话功能"),
        ("user:read",  "查看用户列表"),
        ("user:write", "创建/编辑用户"),
        ("user:delete","删除用户"),
        ("role:write", "创建/编辑角色"),
        ("audit:read", "查看审计日志"),
    ]
    for code, desc in default_perms:
        if not db.query(Permission).filter(Permission.code == code).first():
            db.add(Permission(code=code, description=desc))
    db.commit()

def _validate_security_config() -> None:
    insecure = {"change-me-in-production-please", "replace_with_a_long_random_string"}
    if settings.APP_ENV.lower() == "production" and settings.JWT_SECRET_KEY.strip() in insecure:
        raise RuntimeError("JWT_SECRET_KEY 未正确配置，拒绝启动。")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

_validate_security_config()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix = settings.API_PREFIX
app.include_router(auth.router,      prefix=prefix)
app.include_router(users.router,     prefix=prefix)
app.include_router(chat.router,      prefix=prefix)
app.include_router(knowledge.router, prefix=prefix)
app.include_router(dataset_vector.router, prefix=prefix)
app.include_router(experiments.router, prefix=prefix)


@app.get("/health")
def health():
    return {"status": "ok", "version": settings.APP_VERSION}
