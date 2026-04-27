from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class SessionCreate(BaseModel):
    name: str = "新对话"
    legal_domain: str = ""
    kb_ids: list[int] = []


class SessionUpdate(BaseModel):
    name: str | None = None
    legal_domain: str | None = None
    kb_ids: list[int] | None = None


class SessionOut(BaseModel):
    id: int
    session_uuid: str
    name: str
    legal_domain: str
    kb_ids: list[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    session_uuid: str
    question: str
    legal_domain: str = ""
    kb_ids: list[int] | None = None
    top_k: int = 6


class CitationOut(BaseModel):
    id: int
    dataset: str
    source_name: str
    legal_domain: str
    snippet: str
    score: float
    relevance: str

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    intent: str
    coverage: str
    citations: list[CitationOut] = []
    created_at: datetime

    class Config:
        from_attributes = True
