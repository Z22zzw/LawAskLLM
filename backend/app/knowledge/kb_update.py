import json
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

from app.core import config
from app.rag.legal_domain_map import map_cail_to_domain, map_jec_subject_to_domain
from app.knowledge.vector_store import get_chroma_vector_store


def _chroma_safe_metadata(meta: dict) -> dict:
    """
    Chroma 元数据仅允许 str / int / float / bool。
    JSON 里常见 `"type": null` 等会使 `.get("type", "")` 仍为 None，底层 SQLite 可能报 bindings 类错误。
    """
    out: dict = {}
    for k, v in meta.items():
        if v is None:
            out[k] = ""
        elif isinstance(v, (str, int, float, bool)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


def _options_to_text(option_list: dict) -> str:
    # 保持 A/B/C/D 顺序更利于一致性；如果数据中不是 A-D，也做兜底排序。
    order = ["A", "B", "C", "D", "E", "F"]
    keys = list(option_list.keys())
    keys_sorted = sorted(keys, key=lambda k: order.index(k) if k in order else 999)
    return "\n".join([f"{k}: {option_list[k]}" for k in keys_sorted])


def _make_jec_qa_entry_text(entry: dict) -> str:
    statement = entry.get("statement", "").strip()
    option_list = entry.get("option_list", {}) or {}
    options_text = _options_to_text(option_list)
    subject = entry.get("subject", "")
    subject_part = f"\n科目：{subject}" if subject else ""

    # 作为检索证据：仅包含题干与选项（不把训练集“标准答案”直接塞进证据，避免模型在检索到答案后失去解释性）
    return f"题干：{statement}\n选项：\n{options_text}{subject_part}"


def _entry_to_doc(entry: dict, dataset_name: str, split_name: str) -> "object":
    """
    返回 langchain Document（用类型字符串避免在某些环境下的导入报错时影响主流程）。
    """
    from langchain_core.documents import Document

    entry_id = entry.get("id", "")
    subject = entry.get("subject") or ""
    doc_text = _make_jec_qa_entry_text(entry)
    legal_domain = map_jec_subject_to_domain(subject)
    entry_type = entry.get("type")
    if entry_type is None:
        entry_type = ""

    return Document(
        page_content=doc_text,
        metadata=_chroma_safe_metadata(
            {
                "dataset": dataset_name,
                "split": split_name,
                "id": entry_id,
                "subject": subject,
                "type": entry_type,
                "legal_domain": legal_domain,
            }
        ),
    )


def load_jec_qa_jsonl(path: Path, dataset_name: str, split_name: str, max_items: Optional[int] = None):
    """
    该数据集文件是“一行一个 JSON 对象”（JSON Lines）。
    """
    docs: List[object] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            docs.append(_entry_to_doc(entry, dataset_name=dataset_name, split_name=split_name))
            if max_items is not None and idx + 1 >= max_items:
                break
    return docs


def chunk_documents(docs: List[object]) -> List[object]:
    """
    仅在文档过长时切分；避免切分导致 ids/增量去重逻辑复杂。
    """
    if not docs:
        return docs

    # 判定是否需要切分：只要有一个超长就切分全部（简单策略）。
    need_split = any(len(d.page_content or "") > config.EMBEDDING_CHUNK_SIZE for d in docs)
    if not need_split:
        return docs

    splitter = _get_recursive_splitter()
    return splitter.split_documents(docs)


def build_jec_qa_documents(
    dataset_dir: Path,
    splits: Iterable[str] = ("0_train.json", "1_train.json", "0_test.json", "1_test.json"),
    max_items: Optional[int] = None,
) -> List[object]:
    dataset_name = "jec-qa"

    all_docs: List[object] = []
    for file_name in splits:
        path = dataset_dir / file_name
        if not path.exists():
            raise FileNotFoundError(f"找不到文件：{path}")

        # split_name：用于元数据展示（0_train/1_test 等）
        split_name = file_name.replace(".json", "")
        docs = load_jec_qa_jsonl(path, dataset_name=dataset_name, split_name=split_name, max_items=max_items)
        all_docs.extend(docs)

    return chunk_documents(all_docs)


def update_vector_store_from_jec_qa(
    rebuild: bool = False,
    splits: Iterable[str] = ("0_train.json", "1_train.json", "0_test.json", "1_test.json"),
    max_items: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
):
    """
    构建/更新向量库（JEC-QA）。

    progress_callback(done_count, total_count, message)：
    每完成一批嵌入并写入 Chroma 后调用，便于前端刷新进度（否则全量一次 add_documents 会长时间无反馈）。
    """
    from app.knowledge.vector_store import reset_vector_store

    if rebuild:
        reset_vector_store()

    vector_store = get_chroma_vector_store()
    if progress_callback:
        progress_callback(0, 0, "JEC-QA：正在从磁盘加载 JSON 并组卷（此步不入网，大文件可能需数秒）…")

    docs = build_jec_qa_documents(dataset_dir=config.JEC_QA_DIR, splits=splits, max_items=max_items)
    if not docs:
        return 0

    n = len(docs)
    batch_size = config.KB_EMBED_BATCH_SIZE
    if progress_callback:
        progress_callback(
            0,
            n,
            f"JEC-QA：共 {n} 条，开始调用 DashScope 嵌入（每批约 {batch_size} 条）…",
        )
    for start in range(0, n, batch_size):
        batch = docs[start : start + batch_size]
        vector_store.add_documents(batch)
        done = min(start + len(batch), n)
        if progress_callback:
            progress_callback(
                done,
                n,
                f"JEC-QA：已向量化并写入 {done}/{n} 条（DashScope 嵌入 + Chroma，请稍候）",
            )

    vector_store.persist()
    return n


def _parse_cail_line(line: str) -> Optional[Tuple[str, str]]:
    """
    CAIL2018 small charges 的每行格式通常为：
      <案件事实/文本>\t<罪名标签>
    """
    line = line.rstrip("\n")
    if not line:
        return None
    parts = line.split("\t")
    if len(parts) < 2:
        return None
    text = parts[0].strip()
    label = parts[1].strip()
    if not text or not label:
        return None
    return text, label


def _get_recursive_splitter():
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        from langchain.text_splitter import RecursiveCharacterTextSplitter  # 兼容旧版本

    return RecursiveCharacterTextSplitter(
        chunk_size=config.EMBEDDING_CHUNK_SIZE,
        chunk_overlap=config.EMBEDDING_CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    )


def update_vector_store_from_cail2018(
    rebuild: bool = False,
    splits: Iterable[str] = ("train.txt", "dev.txt", "test.txt"),
    max_items_per_split: Optional[int] = None,
    batch_chunk_docs_size: int = 64,
    progress_callback: Optional[Callable[[int, str], None]] = None,
):
    """
    构建/更新向量库（CAIL2018 small charges）。

    说明：
    - 为避免一次性加载超大文件，本实现“逐行读取 + 分块 + 分批写入”。
    - `max_items_per_split` 是每个 split 最多入库的“样本条数（case数）”，不等于 chunk 数。
    - progress_callback(cumulative_chunks, message)：每写完一批 chunk 调用一次。
    """
    from app.knowledge.vector_store import reset_vector_store

    if rebuild:
        reset_vector_store()

    vector_store = get_chroma_vector_store()
    splitter = _get_recursive_splitter()

    dataset_name = "cail2018"
    # 使用 label.txt 做“罪名标准化/校验”（确保元数据展示更稳定）
    labels_set = set()
    label_path = config.CAIL_2018_DIR / "label.txt"
    if label_path.exists():
        with label_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip()
                if s:
                    labels_set.add(s)

    total_chunks_added = 0
    for file_name in splits:
        file_path = config.CAIL_2018_DIR / file_name
        if not file_path.exists():
            raise FileNotFoundError(f"找不到文件：{file_path}")

        split_name = file_name.replace(".txt", "")
        case_count = 0
        chunk_batch: List[object] = []

        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_idx, line in enumerate(f):
                if max_items_per_split is not None and case_count >= max_items_per_split:
                    break

                parsed = _parse_cail_line(line)
                if not parsed:
                    continue

                text, label = parsed
                from langchain_core.documents import Document

                subject = label
                if labels_set:
                    # 优先使用 label.txt 中存在的标准词
                    if subject not in labels_set and subject.strip() in labels_set:
                        subject = subject.strip()

                legal_domain = map_cail_to_domain(subject)
                base_doc = Document(
                    page_content=text,
                    metadata=_chroma_safe_metadata(
                        {
                            "dataset": dataset_name,
                            "split": split_name,
                            "id": str(case_count),
                            "subject": subject,
                            "type": "charge",
                            "legal_domain": legal_domain,
                        }
                    ),
                )

                chunks = splitter.split_documents([base_doc])
                chunk_batch.extend(chunks)
                case_count += 1

                if len(chunk_batch) >= batch_chunk_docs_size:
                    vector_store.add_documents(chunk_batch)
                    total_chunks_added += len(chunk_batch)
                    chunk_batch = []
                    if progress_callback:
                        progress_callback(
                            total_chunks_added,
                            f"CAIL2018（{split_name}）：已写入 {total_chunks_added} 个向量块…",
                        )

        # flush
        if chunk_batch:
            vector_store.add_documents(chunk_batch)
            total_chunks_added += len(chunk_batch)
            if progress_callback:
                progress_callback(
                    total_chunks_added,
                    f"CAIL2018（{split_name}）：已写入 {total_chunks_added} 个向量块…",
                )

    vector_store.persist()
    return total_chunks_added

