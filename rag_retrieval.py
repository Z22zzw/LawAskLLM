"""
向量检索层：多路检索、MMR、RRF 融合、关键词重排序。

所有函数均不依赖 LLM。LLM 侧的意图路由 / 关键词提取 / 证据评估在 rag_llm.py。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import config
from legal_domain_map import LEGAL_DOMAIN_LABELS, normalize_legal_domain_for_filter

FilterType = Optional[Dict[str, Any]]

_EVIDENCE_SNIPPET_MAX = 600

_EXAM_HINTS = ("选择题", "选项", "下列", "司考", "法考", "哪项", "正确的是", "哪一", "ABCD")
_CASE_HINTS = ("被告人", "检察院", "指控", "经审理", "判决", "本院认为", "罪名", "刑事拘留", "逮捕")


# ──────────────────────── 文本清洗 / 格式化 ────────────────────────

def clean_evidence_text(text: str) -> str:
    """
    清洗向量检索证据，避免把训练集里的"标准答案"直接作为证据展示/喂给模型。
    """
    if not text:
        return ""
    text = re.sub(r"标准答案：.*?(?=\n|$)", "", text, flags=re.DOTALL)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def format_context(doc, idx: int) -> str:
    md = doc.metadata or {}
    dataset = md.get("dataset", "unknown")
    split = md.get("split", "")
    doc_id = md.get("id", "")
    subject = md.get("subject", "")
    ld = md.get("legal_domain", "")
    title = f"{dataset}/{split}/{doc_id}"
    if ld:
        title += f"（领域：{LEGAL_DOMAIN_LABELS.get(ld, ld)}）"
    if subject:
        title += f"（科目：{subject}）"
    snippet = clean_evidence_text(doc.page_content or "").strip()
    if len(snippet) > _EVIDENCE_SNIPPET_MAX:
        snippet = snippet[:_EVIDENCE_SNIPPET_MAX] + "..."
    return f"[{idx}] {title}\n{snippet}"


# ──────────────────────── 去重 / 融合 / 重排 ────────────────────────

def _doc_dedup_key(doc) -> str:
    md = doc.metadata or {}
    body = (doc.page_content or "")[:120]
    return f"{md.get('dataset','')}|{md.get('split','')}|{md.get('id','')}|{hash(body)}"


def _interleave_merge(docs_a: List, docs_b: List, max_n: int) -> List:
    seen: set = set()
    out: List = []
    n = max(len(docs_a), len(docs_b))
    for i in range(n):
        for part in (docs_a, docs_b):
            if i < len(part):
                d = part[i]
                k = _doc_dedup_key(d)
                if k not in seen:
                    seen.add(k)
                    out.append(d)
                    if len(out) >= max_n:
                        return out
    return out[:max_n]


def rrf_fuse(ranked_lists: List[List], k: int = 60) -> List:
    """
    Reciprocal Rank Fusion：score(d) = Σ 1/(k + rank_i(d))。
    """
    scores: Dict[str, float] = {}
    first_doc: Dict[str, Any] = {}
    for docs in ranked_lists:
        for rank, d in enumerate(docs, start=1):
            dk = _doc_dedup_key(d)
            first_doc.setdefault(dk, d)
            scores[dk] = scores.get(dk, 0.0) + 1.0 / (k + rank)
    keys_sorted = sorted(scores.keys(), key=lambda kk: scores[kk], reverse=True)
    return [first_doc[kk] for kk in keys_sorted]


def _rerank_by_keyword_relevance(docs: List, keywords: List[str], question: str) -> List:
    """
    按关键词命中数对检索结果做二次排序，命中多的排前。
    """
    if not keywords or not docs:
        return docs
    all_kw = [k.lower() for k in keywords]
    scored: List[tuple] = []
    for idx, doc in enumerate(docs):
        content = (doc.page_content or "").lower()
        subject = ((doc.metadata or {}).get("subject") or "").lower()
        text = content + " " + subject
        hits = sum(1 for k in all_kw if k in text)
        scored.append((-hits, idx, doc))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in scored]


# ──────────────────────── 数据源过滤 / MMR / 关键词增强 ────────────────────────

def _filter_for_dataset(dataset_val: str, legal_domain: Optional[str]) -> FilterType:
    if legal_domain:
        return {"$and": [{"dataset": dataset_val}, {"legal_domain": legal_domain}]}
    return {"dataset": dataset_val}


def _search_with_optional_mmr(
    vector_store,
    query: str,
    k: int,
    filt: FilterType,
    use_mmr: bool,
    trace: List[str],
) -> List:
    if k <= 0:
        return []
    kwargs: Dict[str, Any] = {"k": k}
    if filt:
        kwargs["filter"] = filt
    if use_mmr:
        try:
            fetch_k = max(k, config.RETRIEVAL_MMR_FETCH_K)
            return vector_store.max_marginal_relevance_search(
                query,
                k=k,
                fetch_k=fetch_k,
                lambda_mult=config.RETRIEVAL_MMR_LAMBDA,
                filter=filt,
            )
        except Exception:
            trace.append("检索：MMR 去重不可用，回退到相似度检索（mmr_fallback）")
    return vector_store.similarity_search(query, **kwargs)


def _keyword_enhanced_search(
    vector_store,
    keywords: List[str],
    k_per_keyword: int,
    filt: FilterType,
    trace: List[str],
) -> List:
    """
    对每个关键词单独做一次小规模向量检索，补充主查询可能遗漏的证据。
    """
    all_docs: List = []
    seen: set = set()
    for kw in keywords[:5]:
        try:
            kwargs: Dict[str, Any] = {"k": k_per_keyword}
            if filt:
                kwargs["filter"] = filt
            docs = vector_store.similarity_search(kw, **kwargs)
            for d in docs:
                dk = _doc_dedup_key(d)
                if dk not in seen:
                    seen.add(dk)
                    all_docs.append(d)
        except Exception:
            continue
    if all_docs:
        trace.append(f"步骤3-b：关键词增强检索补充了 {len(all_docs)} 条证据（keyword_search）")
    return all_docs


# ──────────────────────── 数据源策略推断 ────────────────────────

def auto_source_mode(question: str) -> str:
    e = sum(1 for h in _EXAM_HINTS if h in question)
    c = sum(1 for h in _CASE_HINTS if h in question)
    if e > c + 1:
        return "jec_only"
    if c > e + 1:
        return "cail_only"
    return "balanced"


def resolve_source_mode(source_mode: str, question: str) -> str:
    mode = (source_mode or "auto").strip().lower()
    if mode == "auto":
        return auto_source_mode(question)
    if mode not in ("balanced", "jec_only", "cail_only"):
        return "balanced"
    return mode


# ──────────────────────── 主入口：单查询检索 ────────────────────────

def retrieve_documents(
    vector_store,
    question: str,
    top_k: int,
    source_mode: str,
    use_mmr: bool,
    use_rrf: bool = True,
    trace: Optional[List[str]] = None,
    legal_domain: Optional[str] = None,
    query_keywords: Optional[Dict[str, List[str]]] = None,
) -> List:
    """
    单查询按数据源策略检索文档，支持可选的关键词增强 + RRF 融合 + 重排。
    """
    trace = trace if trace is not None else []
    ld = normalize_legal_domain_for_filter(legal_domain)
    if ld:
        trace.append(f"检索范围：按法律领域「{ld}」过滤（legal_domain_filter）")

    mode = resolve_source_mode(source_mode, question)
    trace.append(f"检索模式：{mode}（retrieve_mode）")

    jec_f = _filter_for_dataset(config.DATASET_JEC_QA, ld)
    cail_f = _filter_for_dataset(config.DATASET_CAIL2018, ld)

    # Phase 1：语义检索（单源或双源均衡）
    if mode == "jec_only":
        semantic_docs = _search_with_optional_mmr(vector_store, question, top_k, jec_f, use_mmr, trace)
    elif mode == "cail_only":
        semantic_docs = _search_with_optional_mmr(vector_store, question, top_k, cail_f, use_mmr, trace)
    else:
        k_jec = (top_k + 1) // 2
        k_cail = top_k - k_jec
        docs_jec = _search_with_optional_mmr(vector_store, question, k_jec, jec_f, use_mmr, trace)
        docs_cail = _search_with_optional_mmr(vector_store, question, k_cail, cail_f, use_mmr, trace)
        semantic_docs = _interleave_merge(docs_jec, docs_cail, top_k)
        if len(semantic_docs) < top_k:
            extra_filt: FilterType = {"legal_domain": ld} if ld else None
            extra = vector_store.similarity_search(question, k=top_k + len(semantic_docs), filter=extra_filt)
            existing_keys = {_doc_dedup_key(x) for x in semantic_docs}
            for d in extra:
                dk = _doc_dedup_key(d)
                if dk not in existing_keys:
                    semantic_docs.append(d)
                    existing_keys.add(dk)
                if len(semantic_docs) >= top_k:
                    break

    # Phase 2：关键词增强 + RRF 融合 + 重排（可关闭，用于消融）
    if not use_rrf:
        trace.append("步骤4：已关闭 RRF/关键词重排（ablation:no_rrf）")
    elif query_keywords:
        specific_terms = list(query_keywords.get("specific_terms") or [])
        broad_topics = list(query_keywords.get("broad_topics") or [])
        if specific_terms or broad_topics:
            base_filt: FilterType = {"legal_domain": ld} if ld else None
            kw_docs = (
                _keyword_enhanced_search(vector_store, specific_terms, 2, base_filt, trace)
                if specific_terms
                else []
            )
            fused = rrf_fuse([semantic_docs, kw_docs]) if kw_docs else list(semantic_docs)
            fused = _rerank_by_keyword_relevance(fused, specific_terms + broad_topics, question)
            semantic_docs = fused
            trace.append("步骤4：多路检索融合排序 — RRF 融合 + 关键词相关性重排序（dual_retrieval:rrf）")

    return semantic_docs[:top_k]


# ──────────────────────── 多查询检索（LLM 给出 search_queries） ────────────────────────

def retrieve_with_multi_queries(
    vector_store,
    question: str,
    search_queries: List[str],
    top_k: int,
    source_mode: str,
    use_mmr: bool,
    use_rrf: bool,
    legal_domain: Optional[str],
    query_keywords: Optional[Dict[str, List[str]]],
    trace: List[str],
) -> List:
    """
    使用 LLM 意图路由给出的 search_queries 做多路检索 + RRF 融合。
    search_queries 为空或与原问题相同时，退化为仅用原问题检索。
    """
    base_docs = retrieve_documents(
        vector_store,
        question,
        top_k,
        source_mode,
        use_mmr,
        use_rrf=use_rrf,
        trace=trace,
        legal_domain=legal_domain,
        query_keywords=query_keywords,
    )
    queries = [
        q for q in (search_queries or [])
        if q and q.strip() and q.strip() != (question or "").strip()
    ]
    if not queries:
        return base_docs

    ranked_lists: List[List] = [base_docs]
    for q in queries[:3]:
        try:
            extra = retrieve_documents(
                vector_store,
                q,
                top_k,
                source_mode,
                use_mmr,
                use_rrf=use_rrf,
                trace=trace,
                legal_domain=legal_domain,
                query_keywords=None,
            )
            if extra:
                ranked_lists.append(extra)
        except Exception:
            continue
    fused = rrf_fuse(ranked_lists)
    trace.append(
        f"步骤3+：使用 LLM 意图路由的 {len(queries)} 条 search_queries 做多路检索并 RRF 融合"
        "（chain:multi_query_retrieve）"
    )
    return fused[:top_k] if fused else base_docs
