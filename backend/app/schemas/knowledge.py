from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class KbCreate(BaseModel):
    name: str
    description: str = ""
    legal_domains: list[str] = []


class KbUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    legal_domains: list[str] | None = None


class KbOut(BaseModel):
    id: int
    name: str
    description: str
    legal_domains: list[str]
    vector_collection: str
    embed_model: str
    created_at: datetime
    updated_at: datetime
    doc_count: int = 0

    class Config:
        from_attributes = True


class DocOut(BaseModel):
    id: int
    kb_id: int
    filename: str
    file_type: str
    file_size: int
    status: str
    error_msg: str
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class VectorCollectionStats(BaseModel):
    collection_name: str
    kb_id: int
    kb_name: str
    vector_count: int
    size_mb: float
    status: str
