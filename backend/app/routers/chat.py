from __future__ import annotations
import uuid
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.chat import ChatSession, ChatMessage, MessageCitation
from app.models.user import User
from app.schemas.chat import SessionCreate, SessionUpdate, SessionOut, ChatRequest, MessageOut, CitationOut
from app.services import rag_bridge

router = APIRouter(prefix="/chat", tags=["对话"])


def _get_session(db: Session, session_uuid: str, user: User) -> ChatSession:
    s = db.query(ChatSession).filter(ChatSession.session_uuid == session_uuid).first()
    if not s:
        raise HTTPException(status_code=404, detail="会话不存在")
    if s.user_id and s.user_id != user.id and not user.is_superadmin:
        raise HTTPException(status_code=403, detail="无权访问该会话")
    return s


# ── 会话 CRUD ──

@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(body: SessionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = ChatSession(
        session_uuid=str(uuid.uuid4()),
        user_id=user.id,
        name=body.name,
        legal_domain=body.legal_domain,
        kb_ids=body.kb_ids,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(limit: int = 30, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/sessions/{session_uuid}", response_model=SessionOut)
def get_session(session_uuid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_session(db, session_uuid, user)


@router.patch("/sessions/{session_uuid}", response_model=SessionOut)
def update_session(session_uuid: str, body: SessionUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _get_session(db, session_uuid, user)
    if body.name is not None:
        s.name = body.name
    if body.legal_domain is not None:
        s.legal_domain = body.legal_domain
    if body.kb_ids is not None:
        s.kb_ids = body.kb_ids
    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(s)
    return s


@router.delete("/sessions/{session_uuid}", status_code=204)
def delete_session(session_uuid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _get_session(db, session_uuid, user)
    db.delete(s)
    db.commit()


# ── 消息 ──

@router.get("/sessions/{session_uuid}/messages", response_model=list[MessageOut])
def list_messages(session_uuid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _get_session(db, session_uuid, user)
    return s.messages


@router.get("/messages/{message_id}/citations", response_model=list[CitationOut])
def get_citations(message_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(MessageCitation).filter(MessageCitation.message_id == message_id).all()


# ── 主对话接口（SSE 流式） ──

@router.post("/completions")
def chat_completion(body: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _get_session(db, body.session_uuid, user)

    history_msgs = s.messages[-10:]
    chat_history = [
        (history_msgs[i].content, history_msgs[i + 1].content)
        for i in range(0, len(history_msgs) - 1, 2)
        if history_msgs[i].role == "user" and i + 1 < len(history_msgs)
    ]

    def event_stream():
        yield _sse("chain_trace", {"step": "正在分析问题意图…"})

        result = rag_bridge.answer(
            body.question,
            legal_domain=body.legal_domain or s.legal_domain,
            chat_history=chat_history,
            long_term_summary=s.summary,
            top_k=body.top_k,
        )

        for step in result.get("chain_trace") or []:
            yield _sse("chain_trace", {"step": step})

        answer_text = result.get("answer", "")
        for chunk in _chunk_text(answer_text, 80):
            yield _sse("answer_chunk", {"content": chunk})

        citations_data = []
        raw_cites = result.get("citations") or []
        user_msg = ChatMessage(session_id=s.id, role="user", content=body.question)
        db.add(user_msg)
        db.flush()

        ai_msg = ChatMessage(
            session_id=s.id,
            role="assistant",
            content=answer_text,
            intent=result.get("intent", ""),
            coverage=result.get("coverage", ""),
            retrieval_ms=result.get("_elapsed_ms", 0),
        )
        db.add(ai_msg)
        db.flush()

        for c in raw_cites:
            cite = MessageCitation(
                message_id=ai_msg.id,
                dataset=c.get("dataset", ""),
                source_name=c.get("subject", ""),
                legal_domain=c.get("legal_domain", ""),
                snippet=c.get("snippet", ""),
                score=float(c.get("score", 0)),
                relevance=c.get("relevance", ""),
            )
            db.add(cite)
            citations_data.append({
                "dataset": cite.dataset,
                "source_name": cite.source_name,
                "legal_domain": cite.legal_domain,
                "snippet": cite.snippet,
                "score": cite.score,
                "relevance": cite.relevance,
            })

        s.updated_at = datetime.utcnow()

        new_turn_count = sum(1 for m in s.messages if m.role == "user") + 1
        if new_turn_count >= 4 and new_turn_count % 4 == 0:
            pairs = chat_history + [(body.question, answer_text)]
            new_summary = rag_bridge.summarize(pairs)
            if new_summary:
                s.summary = new_summary
                if s.name == "新对话":
                    s.name = new_summary.strip().splitlines()[0][:20] or "新对话"

        db.commit()

        yield _sse("citations", {"data": citations_data})
        yield _sse("done", {"message_id": ai_msg.id, "session_name": s.name})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, size: int):
    for i in range(0, len(text), size):
        yield text[i:i + size]
