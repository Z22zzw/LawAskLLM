from __future__ import annotations
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.deps import get_current_user
from app.models.knowledge import KnowledgeBase, KnowledgeDoc
from app.models.user import User
from app.schemas.knowledge import (
    DocOut,
    KbCreate,
    KbIndexJobCreate,
    KbIndexJobStatus,
    KbOut,
    KbUpdate,
    VectorCollectionStats,
)

router = APIRouter(prefix="/knowledge-bases", tags=["知识库"])

UPLOAD_DIR = settings.VECTOR_DB_DIR.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_kb_index_jobs: Dict[str, Dict[str, Any]] = {}
_kb_index_lock = threading.Lock()


def _kb_index_log(job_id: str, msg: str) -> None:
    with _kb_index_lock:
        j = _kb_index_jobs.get(job_id)
        if not j:
            return
        j.setdefault("logs", []).append(msg)
        if len(j["logs"]) > 400:
            j["logs"] = j["logs"][-300:]


def _run_kb_index_job(job_id: str, kb_id: int) -> None:
    from user_kb_index_service import index_kb_uploaded_documents

    with _kb_index_lock:
        _kb_index_jobs[job_id]["status"] = "running"
        _kb_index_jobs[job_id]["logs"] = []
        _kb_index_jobs[job_id]["error"] = None

    db = SessionLocal()
    try:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise RuntimeError("知识库不存在")
        docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.kb_id == kb_id).order_by(KnowledgeDoc.id.asc()).all()
        if not docs:
            raise RuntimeError("没有可索引的文档，请先上传文件")

        for d in docs:
            d.status = "indexing"
            d.error_msg = ""
            d.chunk_count = 0
        db.commit()

        rows = [(d.id, d.filename, d.file_type) for d in docs]
        upload_dir = UPLOAD_DIR / str(kb_id)
        total, per_doc = index_kb_uploaded_documents(
            kb.vector_collection,
            kb.name,
            upload_dir,
            rows,
            log=lambda m: _kb_index_log(job_id, m),
        )

        for d in docs:
            cnt = int(per_doc.get(d.id, 0))
            d.chunk_count = cnt
            d.status = "indexed" if cnt > 0 else "failed"
            if cnt == 0:
                d.error_msg = "无有效文本或文件缺失"
        kb.updated_at = datetime.utcnow()
        db.commit()

        with _kb_index_lock:
            _kb_index_jobs[job_id]["status"] = "done"
        _kb_index_log(job_id, f"索引完成，共 {total} 个向量块。")
    except Exception as e:
        err = str(e)
        with _kb_index_lock:
            _kb_index_jobs[job_id]["status"] = "error"
            _kb_index_jobs[job_id]["error"] = err
        _kb_index_log(job_id, f"失败：{err}")
        try:
            db.rollback()
            kb2 = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if kb2:
                for d in db.query(KnowledgeDoc).filter(KnowledgeDoc.kb_id == kb_id).all():
                    if d.status == "indexing":
                        d.status = "failed"
                        d.error_msg = err[:500]
                kb2.updated_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _kb_or_404(db: Session, kb_id: int) -> KnowledgeBase:
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


@router.get("", response_model=list[KbOut])
def list_kbs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    kbs = db.query(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()).all()
    result = []
    for kb in kbs:
        out = KbOut.model_validate(kb)
        out.doc_count = len(kb.documents)
        result.append(out)
    return result


@router.post("", response_model=KbOut, status_code=201)
def create_kb(body: KbCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    slug = body.name.replace(" ", "_").lower()[:32]
    collection = f"law_rag_{user.id}_{slug}"
    kb = KnowledgeBase(
        name=body.name,
        description=body.description,
        legal_domains=body.legal_domains,
        vector_collection=collection,
        created_by=user.id,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


@router.get("/{kb_id}", response_model=KbOut)
def get_kb(kb_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    kb = _kb_or_404(db, kb_id)
    out = KbOut.model_validate(kb)
    out.doc_count = len(kb.documents)
    return out


@router.patch("/{kb_id}", response_model=KbOut)
def update_kb(kb_id: int, body: KbUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    kb = _kb_or_404(db, kb_id)
    if body.name is not None:
        kb.name = body.name
    if body.description is not None:
        kb.description = body.description
    if body.legal_domains is not None:
        kb.legal_domains = body.legal_domains
    db.commit()
    db.refresh(kb)
    return kb


@router.delete("/{kb_id}", status_code=204)
def delete_kb(kb_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    kb = _kb_or_404(db, kb_id)
    db.delete(kb)
    db.commit()


# ── 文档管理 ──

@router.post("/{kb_id}/documents", response_model=DocOut, status_code=201)
async def upload_document(
    kb_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    kb = _kb_or_404(db, kb_id)
    save_dir = UPLOAD_DIR / str(kb_id)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / file.filename
    content = await file.read()
    save_path.write_bytes(content)

    doc = KnowledgeDoc(
        kb_id=kb_id,
        filename=file.filename,
        file_type=Path(file.filename).suffix.lower(),
        file_size=len(content),
        status="pending",
        uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{kb_id}/documents", response_model=list[DocOut])
def list_documents(kb_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    _kb_or_404(db, kb_id)
    return db.query(KnowledgeDoc).filter(KnowledgeDoc.kb_id == kb_id).order_by(KnowledgeDoc.created_at.desc()).all()


@router.delete("/{kb_id}/documents/{doc_id}", status_code=204)
def delete_document(kb_id: int, doc_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.kb_id == kb_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    db.delete(doc)
    db.commit()


@router.post("/{kb_id}/index/start", response_model=KbIndexJobCreate)
def start_kb_vector_index(kb_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    _kb_or_404(db, kb_id)
    job_id = str(uuid.uuid4())
    with _kb_index_lock:
        _kb_index_jobs[job_id] = {"kb_id": kb_id, "status": "pending", "logs": [], "error": None}
    t = threading.Thread(target=_run_kb_index_job, args=(job_id, kb_id), daemon=True)
    t.start()
    return KbIndexJobCreate(job_id=job_id)


@router.get("/{kb_id}/index/jobs/{job_id}", response_model=KbIndexJobStatus)
def kb_index_job_status(kb_id: int, job_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    _kb_or_404(db, kb_id)
    with _kb_index_lock:
        j = _kb_index_jobs.get(job_id)
    if not j or j.get("kb_id") != kb_id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return KbIndexJobStatus(
        job_id=job_id,
        status=j.get("status", "pending"),
        logs=list(j.get("logs") or []),
        error=j.get("error"),
    )


# ── 向量库状态 ──

@router.get("/vector/stats", response_model=list[VectorCollectionStats])
def vector_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    kbs = db.query(KnowledgeBase).all()
    result = []
    for kb in kbs:
        db_path = settings.VECTOR_DB_DIR / kb.vector_collection / "chroma.sqlite3"
        size_mb = round(db_path.stat().st_size / 1024 / 1024, 2) if db_path.exists() else 0.0
        status = "ready" if db_path.exists() else "empty"
        result.append(VectorCollectionStats(
            collection_name=kb.vector_collection,
            kb_id=kb.id,
            kb_name=kb.name,
            vector_count=len(kb.documents),
            size_mb=size_mb,
            status=status,
        ))
    return result
