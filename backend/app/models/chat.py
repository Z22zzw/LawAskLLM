from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), default="新对话")
    legal_domain: Mapped[str] = mapped_column(String(32), default="")
    kb_ids: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    messages: Mapped[list[ChatMessage]] = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(32), default="")
    coverage: Mapped[str] = mapped_column(String(16), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    retrieval_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="messages")
    citations: Mapped[list[MessageCitation]] = relationship("MessageCitation", back_populates="message", cascade="all, delete-orphan")


class MessageCitation(Base):
    __tablename__ = "message_citations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_messages.id", ondelete="CASCADE"))
    kb_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    doc_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    chunk_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    dataset: Mapped[str] = mapped_column(String(64), default="")
    source_name: Mapped[str] = mapped_column(String(255), default="")
    legal_domain: Mapped[str] = mapped_column(String(32), default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    relevance: Mapped[str] = mapped_column(String(16), default="")
    message: Mapped[ChatMessage] = relationship("ChatMessage", back_populates="citations")
