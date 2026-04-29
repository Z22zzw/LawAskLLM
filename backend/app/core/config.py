import os

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings



PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = PROJECT_ROOT / "data"



# Chroma persistent directory（向量数据库）
# 若默认目录不可写（权限 / Docker UID），可设置绝对路径指向可写目录，并与 backend 的 LAWASK_VECTOR_DB_DIR 保持一致。
_VECTOR_OVERRIDE = os.getenv("LAWASK_VECTOR_DB_DIR", "").strip()
VECTOR_DB_DIR = Path(_VECTOR_OVERRIDE).resolve() if _VECTOR_OVERRIDE else PROJECT_ROOT / "向量数据库"

# Windows 下 chroma.sqlite3 常被后端服务或其它进程占用，删除目录需重试
VECTOR_DB_RESET_MAX_ATTEMPTS = max(1, int(os.getenv("VECTOR_DB_RESET_MAX_ATTEMPTS", "20")))
VECTOR_DB_RESET_RETRY_DELAY_SEC = float(os.getenv("VECTOR_DB_RESET_RETRY_DELAY_SEC", "3"))



# Local export of chat histories (历史聊天信息存储)

CHAT_HISTORY_DIR = PROJECT_ROOT / "历史聊天信息存储"

# 实验记录与复盘导出
EXPERIMENT_LOG_DIR = PROJECT_ROOT / "实验记录"
EXPERIMENT_TURNS_JSONL = EXPERIMENT_LOG_DIR / "qa_experiment_turns.jsonl"
EXPERIMENT_EXPORT_DIR = EXPERIMENT_LOG_DIR / "session_exports"



# ---- Dataset paths ----

JEC_QA_DIR = DATA_DIR / "jec-qa" / "JEC-QA"

CAIL_2018_DIR = DATA_DIR / "cail2018" / "cail2018_small_charges" / "cail2018_small_charges"



# 与 kb_update_service 写入 metadata 的 dataset 字段一致

DATASET_JEC_QA = "jec-qa"

DATASET_CAIL2018 = "cail2018"

DATASET_USER_KB = "user_kb"



# ---- Tongyi Embeddings ----

# TongyiEmbeddings uses `DASHSCOPE_API_KEY`.

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

# 嵌入 API 遇 SSL 中断、连接重置等网络抖动时重试（大批量建库时更稳）
DASHSCOPE_EMBED_MAX_RETRIES = max(1, int(os.getenv("DASHSCOPE_EMBED_MAX_RETRIES", "6")))
DASHSCOPE_EMBED_RETRY_BASE_DELAY_SEC = float(os.getenv("DASHSCOPE_EMBED_RETRY_BASE_DELAY_SEC", "2.0"))





def _is_placeholder_key(key: str) -> bool:

    if not key:

        return True

    # 常见占位符（避免误以为“已配置”，实际仍用的是模板文本）

    placeholders = [

        "在此处填写",

        "在此处填",

        "YOUR_",

        "your_",

        "填写你的",

        "deepseek api key",

        "dashscope api key",

    ]

    return any(p.lower() in key.lower() for p in placeholders)





# 如果用户还没把 .env 里的占位符替换成真实 key，则当作未配置

if _is_placeholder_key(DASHSCOPE_API_KEY):

    DASHSCOPE_API_KEY = ""



# ---- LLM 配置（OpenAI 兼容接口）----

# 只保留 LLM_* 一套配置，避免变量名混乱。

LLM_BASE_URL = (

    os.getenv("LLM_BASE_URL")

    or "https://dashscope.aliyuncs.com/compatible-mode/v1"

)



LLM_MODEL = (

    os.getenv("LLM_MODEL")

    or "deepseek-v3.2"

)



LLM_API_KEY = (

    os.getenv("LLM_API_KEY")

    or ""

)



if _is_placeholder_key(LLM_API_KEY):

    LLM_API_KEY = ""



# ---- Retrieval / chunking ----

EMBEDDING_CHUNK_SIZE = int(os.getenv("EMBEDDING_CHUNK_SIZE", "800"))

EMBEDDING_CHUNK_OVERLAP = int(os.getenv("EMBEDDING_CHUNK_OVERLAP", "80"))

# 向量入库时每批文档数（越小界面更新越勤，但 HTTP 次数更多、总耗时可能略增）
KB_EMBED_BATCH_SIZE = max(1, int(os.getenv("KB_EMBED_BATCH_SIZE", "128")))



RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "6"))



# MMR：减轻 CAIL 多块近重复挤占 top_k

RETRIEVAL_USE_MMR_DEFAULT = os.getenv("RETRIEVAL_USE_MMR", "").lower() in ("1", "true", "yes")

RETRIEVAL_MMR_FETCH_K = int(os.getenv("RETRIEVAL_MMR_FETCH_K", "24"))

RETRIEVAL_MMR_LAMBDA = float(os.getenv("RETRIEVAL_MMR_LAMBDA", "0.55"))



# ---- MySQL ----

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")

MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))

MYSQL_USER = os.getenv("MYSQL_USER", "root")

MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")

MYSQL_DB = os.getenv("MYSQL_DB", "law_rag")

# 对话检索策略（由知识库构建页写入，对话页只读）
RUNTIME_RAG_PREFS_PATH = PROJECT_ROOT / "runtime_rag_prefs.json"

# 法律领域（id, 展示名）— 与 legal_domain_map 一致，便于统一从 config 导入
from app.rag.legal_domain_map import LEGAL_DOMAIN_LABELS, LEGAL_DOMAIN_OPTIONS as LEGAL_DOMAIN_CHOICES  # noqa: E402


def _default_vector_db_dir() -> Path:
    raw = os.getenv("LAWASK_VECTOR_DB_DIR", "").strip()
    return Path(raw).resolve() if raw else VECTOR_DB_DIR


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
    MYSQL_HOST: str = MYSQL_HOST
    MYSQL_PORT: int = MYSQL_PORT
    MYSQL_USER: str = MYSQL_USER
    MYSQL_PASSWORD: str = MYSQL_PASSWORD
    MYSQL_DB: str = os.getenv("MYSQL_DB", "law_llm")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            f"?charset=utf8mb4"
        )

    # ── LLM / Embedding ──
    LLM_API_KEY: str = LLM_API_KEY
    LLM_BASE_URL: str = LLM_BASE_URL
    LLM_MODEL: str = LLM_MODEL
    DASHSCOPE_API_KEY: str = DASHSCOPE_API_KEY

    # ── 向量库 ──
    VECTOR_DB_DIR: Path = Field(default_factory=_default_vector_db_dir)

    # ── CORS ──
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
