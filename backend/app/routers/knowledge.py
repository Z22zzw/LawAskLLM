from __future__ import annotations
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models.knowledge import KnowledgeBase, KnowledgeDoc
from app.models.user import User
from app.schemas.knowledge import KbCreate, KbOut, KbUpdate, DocOut, VectorCollectionStats

router = APIRouter(prefix="/knowledge-bases", tags=["知识库"])

UPLOAD_DIR = settings.VECTOR_DB_DIR.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
