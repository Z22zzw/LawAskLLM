from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    legal_domains: Mapped[list] = mapped_column(JSON, default=list)
    vector_collection: Mapped[str] = mapped_column(String(255), nullable=False)
    embed_model: Mapped[str] = mapped_column(String(128), default="text-embedding-v3")
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    documents: Mapped[list[KnowledgeDoc]] = relationship("KnowledgeDoc", back_populates="kb", cascade="all, delete-orphan")


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/indexing/indexed/failed
    error_msg: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    kb: Mapped[KnowledgeBase] = relationship("KnowledgeBase", back_populates="documents")
    chunks: Mapped[list[DocChunk]] = relationship("DocChunk", back_populates="doc", cascade="all, delete-orphan")


class DocChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_docs.id", ondelete="CASCADE"))
    kb_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    vector_id: Mapped[str] = mapped_column(String(255), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    doc: Mapped[KnowledgeDoc] = relationship("KnowledgeDoc", back_populates="chunks")
