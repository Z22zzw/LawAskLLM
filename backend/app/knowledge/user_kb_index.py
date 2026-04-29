"""
将管理台上传的文档分块、嵌入并写入独立 Chroma（与全局 law_rag 分离）。
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from app.core import config
from app.knowledge.kb_update import _chroma_safe_metadata, _get_recursive_splitter
from app.knowledge.vector_store import get_kb_chroma_vector_store


def _read_plain(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("未安装 pypdf，无法处理 PDF。请执行：pip install pypdf") from e
    reader = PdfReader(str(path))
    parts: List[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def load_document_text(path: Path, file_type: str) -> str:
    suf = (file_type or path.suffix or "").lower()
    if suf in (".txt", ".md", ".markdown"):
        return _read_plain(path)
    if suf == ".json":
        return _read_plain(path)
    if suf == ".pdf":
        return _read_pdf(path)
    raise ValueError(f"暂不支持的文件类型：{suf}（支持 .txt .md .json .pdf）")


def index_kb_uploaded_documents(
    vector_collection: str,
    kb_name: str,
    upload_dir: Path,
    doc_rows: List[Tuple[int, str, str]],
    log: Optional[Callable[[str], None]] = None,
) -> Tuple[int, Dict[int, int]]:
    """
    清空该 KB 对应向量目录后，重新索引 doc_rows 中列出的全部文件。

    doc_rows: (doc_id, filename, file_type)
    返回 (chunk 总数, doc_id -> chunk 数)。
    """
    from langchain_core.documents import Document

    def L(msg: str) -> None:
        if log:
            log(msg)

    persist_root = Path(config.VECTOR_DB_DIR) / vector_collection
    if persist_root.exists():
        shutil.rmtree(persist_root)
    persist_root.mkdir(parents=True, exist_ok=True)

    store = get_kb_chroma_vector_store(vector_collection)
    splitter = _get_recursive_splitter()
    total_chunks = 0
    per_doc: dict = {}

    for doc_id, filename, file_type in doc_rows:
        path = upload_dir / filename
        if not path.exists():
            L(f"跳过（文件不存在）：{filename}")
            continue
        try:
            text = load_document_text(path, file_type)
        except Exception as e:
            raise RuntimeError(f"{filename}: {e}") from e
        text = (text or "").strip()
        if not text:
            L(f"跳过（空内容）：{filename}")
            continue

        base = Document(
            page_content=text,
            metadata=_chroma_safe_metadata(
                {
                    "dataset": config.DATASET_USER_KB,
                    "split": filename,
                    "id": str(doc_id),
                    "subject": (kb_name or "")[:120],
                    "type": "upload",
                    "legal_domain": "",
                }
            ),
        )
        chunks = splitter.split_documents([base])
        fixed = []
        for i, ch in enumerate(chunks):
            md = dict(ch.metadata or {})
            md["id"] = f"{doc_id}_{i}"
            ch.metadata = _chroma_safe_metadata(md)
            fixed.append(ch)
        if fixed:
            store.add_documents(fixed)
            total_chunks += len(fixed)
            per_doc[doc_id] = len(fixed)
            L(f"已写入 {filename}：{len(fixed)} 块")
        else:
            per_doc[doc_id] = 0
    store.persist()
    return total_chunks, per_doc
