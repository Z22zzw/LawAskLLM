import os
import sys
from pathlib import Path

# 让 backend 能 import 项目根目录的 RAG 模块
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pydantic import Field
from pydantic_settings import BaseSettings


def _default_vector_db_dir() -> Path:
    raw = os.getenv("LAWASK_VECTOR_DB_DIR", "").strip()
    return Path(raw).resolve() if raw else PROJECT_ROOT / "向量数据库"


class Settings(BaseSettings):
    # ── 应用 ──
    APP_NAME: str = "法律 LLM 平台"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # ── JWT ──
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production-please")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── 数据库 ──
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "law_llm")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            f"?charset=utf8mb4"
        )

    # ── LLM ──
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-v3.2")
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

    # ── 向量库（与根目录 config.VECTOR_DB_DIR 同步，可用环境变量 LAWASK_VECTOR_DB_DIR 覆盖）──
    VECTOR_DB_DIR: Path = Field(default_factory=_default_vector_db_dir)

    # ── CORS ──
    # 公网部署默认包含本机 IP；也可用环境变量 ALLOWED_ORIGINS='["https://a.com"]'（JSON 数组）覆盖
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:80",
        "http://49.235.100.186",
        "http://49.235.100.186:80",
    ]

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
