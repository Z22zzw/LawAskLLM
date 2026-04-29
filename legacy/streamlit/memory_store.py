import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core import config


def _now_utc_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


class MySQLMemoryStore:
    """
    将用户/会话/消息写入 MySQL。
    如果连接或建表失败，会抛出异常；上层在 UI 中可降级到本地内存。
    """

    def __init__(self):
        self._conn = None

    def _get_conn(self):
        import pymysql

        if self._conn is not None:
            return self._conn

        self._conn = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        return self._conn

    def ensure_tables(self):
        conn = self._get_conn()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    created_at DATETIME NOT NULL
                ) DEFAULT CHARSET=utf8mb4;
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    session_uuid CHAR(36) UNIQUE NOT NULL,
                    session_name VARCHAR(255) NOT NULL DEFAULT '新对话',
                    user_id BIGINT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    INDEX (user_id)
                ) DEFAULT CHARSET=utf8mb4;
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    session_id BIGINT NOT NULL,
                    role VARCHAR(16) NOT NULL,
                    content MEDIUMTEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    INDEX (session_id),
                    CONSTRAINT fk_messages_sessions FOREIGN KEY (session_id) REFERENCES sessions(id)
                ) DEFAULT CHARSET=utf8mb4;
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS session_summaries (
                    session_id BIGINT PRIMARY KEY,
                    summary_text MEDIUMTEXT NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT fk_session_summaries_sessions FOREIGN KEY (session_id) REFERENCES sessions(id)
                ) DEFAULT CHARSET=utf8mb4;
                """
            )

            # 兼容旧库：如果 sessions 表缺少 session_name，则补上
            try:
                cursor.execute("ALTER TABLE sessions ADD COLUMN session_name VARCHAR(255) NOT NULL DEFAULT '新对话'")
            except Exception:
                # 已存在则忽略
                pass

    def create_session(self) -> str:
        """
        返回一个 session_uuid（用于 UI 回放/继续对话等）。
        """
        conn = self._get_conn()
        session_uuid = str(uuid.uuid4())
        now = datetime.utcnow()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sessions (session_uuid, session_name, user_id, created_at, updated_at)
                VALUES (%s, %s, NULL, %s, %s)
                """,
                (session_uuid, "新对话", now, now),
            )
        return session_uuid

    def save_message(self, session_uuid: str, role: str, content: str):
        conn = self._get_conn()
        now = datetime.utcnow()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO messages (session_id, role, content, created_at)
                SELECT id, %s, %s, %s FROM sessions WHERE session_uuid=%s
                """,
                (role, content, now, session_uuid),
            )
            cursor.execute(
                """
                UPDATE sessions SET updated_at=%s WHERE session_uuid=%s
                """,
                (now, session_uuid),
            )

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT session_uuid, session_name, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
        return rows

    def get_session_name(self, session_uuid: str) -> str:
        conn = self._get_conn()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT session_name FROM sessions WHERE session_uuid=%s",
                (session_uuid,),
            )
            row = cursor.fetchone()
        return (row or {}).get("session_name") or ""

    def update_session_name(self, session_uuid: str, session_name: str):
        conn = self._get_conn()
        now = datetime.utcnow()
        name = (session_name or "").strip()[:255] or "新对话"
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE sessions SET session_name=%s, updated_at=%s WHERE session_uuid=%s",
                (name, now, session_uuid),
            )

    def delete_session(self, session_uuid: str):
        """
        删除会话（包含 messages / summaries）。
        """
        conn = self._get_conn()
        with conn.cursor() as cursor:
            # 先删子表，避免外键约束
            cursor.execute(
                """
                DELETE m FROM messages m
                JOIN sessions s ON s.id=m.session_id
                WHERE s.session_uuid=%s
                """,
                (session_uuid,),
            )
            cursor.execute(
                """
                DELETE ss FROM session_summaries ss
                JOIN sessions s ON s.id=ss.session_id
                WHERE s.session_uuid=%s
                """,
                (session_uuid,),
            )
            cursor.execute("DELETE FROM sessions WHERE session_uuid=%s", (session_uuid,))

    def get_messages(self, session_uuid: str) -> List[Dict[str, Any]]:
        """
        返回形如：[{role:'user'|'assistant', content:'...', created_at:'...'}, ...]
        """
        conn = self._get_conn()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.role, m.content, m.created_at
                FROM messages m
                JOIN sessions s ON s.id=m.session_id
                WHERE s.session_uuid=%s
                ORDER BY m.id ASC
                """,
                (session_uuid,),
            )
            rows = cursor.fetchall()
        return rows

    def get_session_summary(self, session_uuid: str) -> str:
        conn = self._get_conn()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT ss.summary_text
                FROM session_summaries ss
                JOIN sessions s ON s.id=ss.session_id
                WHERE s.session_uuid=%s
                """,
                (session_uuid,),
            )
            row = cursor.fetchone()
            if not row:
                return ""
            return row.get("summary_text", "") or ""

    def update_session_summary(self, session_uuid: str, summary_text: str):
        conn = self._get_conn()
        now = datetime.utcnow()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO session_summaries (session_id, summary_text, updated_at)
                SELECT s.id, %s, %s FROM sessions s WHERE s.session_uuid=%s
                ON DUPLICATE KEY UPDATE
                    summary_text=VALUES(summary_text),
                    updated_at=VALUES(updated_at)
                """,
                (summary_text, now, session_uuid),
            )

    def export_chat_to_jsonl(self, session_uuid: str, out_path: str) -> int:
        """
        可选：把会话导出到历史聊天信息存储目录，方便论文展示。
        """
        conn = self._get_conn()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.role, m.content, m.created_at
                FROM messages m
                JOIN sessions s ON s.id = m.session_id
                WHERE s.session_uuid=%s
                ORDER BY m.id ASC
                """,
                (session_uuid,),
            )
            rows = cursor.fetchall()

        import json

        count = 0
        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                count += 1
        return count


class InMemoryChatStore:
    """
    MySQL 未配置或连接失败时的降级实现。
    """

    def __init__(self):
        self._store: Dict[str, List[Dict[str, Any]]] = {}
        self._summaries: Dict[str, str] = {}
        self._created_at: Dict[str, str] = {}
        self._updated_at: Dict[str, str] = {}
        self._names: Dict[str, str] = {}

    def create_session(self) -> str:
        session_uuid = str(uuid.uuid4())
        self._store[session_uuid] = []
        self._summaries[session_uuid] = ""
        self._created_at[session_uuid] = _now_utc_iso()
        self._updated_at[session_uuid] = _now_utc_iso()
        self._names[session_uuid] = "新对话"
        return session_uuid

    def save_message(self, session_uuid: str, role: str, content: str):
        self._store.setdefault(session_uuid, []).append(
            {"role": role, "content": content, "created_at": _now_utc_iso()}
        )
        self._updated_at[session_uuid] = _now_utc_iso()

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        sessions = []
        for sid, msgs in self._store.items():
            sessions.append(
                {
                    "session_uuid": sid,
                    "session_name": self._names.get(sid, "新对话"),
                    "created_at": self._created_at.get(sid),
                    "updated_at": self._updated_at.get(sid),
                }
            )
        sessions.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return sessions[:limit]

    def get_messages(self, session_uuid: str) -> List[Dict[str, Any]]:
        return list(self._store.get(session_uuid, []))

    def get_session_summary(self, session_uuid: str) -> str:
        return self._summaries.get(session_uuid, "") or ""

    def update_session_summary(self, session_uuid: str, summary_text: str):
        self._summaries[session_uuid] = summary_text or ""
        self._updated_at[session_uuid] = _now_utc_iso()

    def get_session_name(self, session_uuid: str) -> str:
        return self._names.get(session_uuid, "") or ""

    def update_session_name(self, session_uuid: str, session_name: str):
        name = (session_name or "").strip()[:255] or "新对话"
        self._names[session_uuid] = name
        self._updated_at[session_uuid] = _now_utc_iso()

    def delete_session(self, session_uuid: str):
        self._store.pop(session_uuid, None)
        self._summaries.pop(session_uuid, None)
        self._created_at.pop(session_uuid, None)
        self._updated_at.pop(session_uuid, None)
        self._names.pop(session_uuid, None)

    def export_chat_to_jsonl(self, session_uuid: str, out_path: str) -> int:
        import json

        rows = self._store.get(session_uuid, [])
        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return len(rows)

