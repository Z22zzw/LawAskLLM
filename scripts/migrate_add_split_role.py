#!/usr/bin/env python3
"""
一次性迁移：为 knowledge_docs 表添加 split_role 列。
如果列已存在则跳过，可安全重复执行。

运行方式（在仓库根目录）：
    cd backend && python ../scripts/migrate_add_split_role.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import text
from app.database import engine  # noqa: E402  — 需要先插入 sys.path

CHECK_SQL = "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='knowledge_docs' AND COLUMN_NAME='split_role'"
ALTER_SQL = "ALTER TABLE knowledge_docs ADD COLUMN split_role VARCHAR(16) NOT NULL DEFAULT 'train' AFTER file_size"

with engine.begin() as conn:
    exists = conn.execute(text(CHECK_SQL)).scalar()
    if exists:
        print("split_role 列已存在，跳过。")
    else:
        conn.execute(text(ALTER_SQL))
        print("split_role 列已添加。")
