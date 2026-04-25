"""
RAG 对话编排（LCEL 链）：
- 入口：answer_question
- 三分支：空输入 / 非法律直答 / 法律 RAG
- 法律 RAG：LLM 意图路由的 search_queries → 多路检索 → 证据相关性评估 → 证据感知生成 → 强制「知识库覆盖」小结

对外公共接口（供 app_chat / rag_agent / 外部脚本使用）：
- answer_question
- summarize_for_memory
- retrieve_documents
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import config
from langchain_core.runnables import RunnableBranch, RunnableLambda
from legal_domain_map import LEGAL_DOMAIN_LABELS, normalize_legal_domain_for_filter
from llm_client import call_llm
from rag_llm import (
    answer_non_legal,
    build_clarify_reply,
    extract_query_keywords,
    generate_bridge_context,
    llm_intent_route,
    needs_clarification,
    score_evidence_relevance,
    summarize_for_memory,
)
from rag_prefs import load_rag_prefs
from rag_retrieval import (
    clean_evidence_text,
    format_context,
    resolve_source_mode,
    retrieve_documents,
    retrieve_with_multi_queries,
)
from vector_store_service import get_chroma_vector_store

__all__ = [
    "answer_question",
    "summarize_for_memory",
    "retrieve_documents",
]

_CITATION_SNIPPET_MAX = 220


# ──────────────────────── 对话历史格式化 ────────────────────────

def _history_blocks(
    chat_history: Optional[List[Tuple[str, str]]],
    long_term_summary: Optional[str],
) -> Tuple[str, str]:
    history_block = ""
    if chat_history:
        tail = chat_history[-4:]
        lines: List[str] = []
        for u, a in tail:
            lines.append(f"用户：{u}")
            lines.append(f"助手：{a}")
        history_block = "对话历史（仅供参考）：\n" + "\n".join(lines) + "\n"

    long_term_block = ""
    if long_term_summary and long_term_summary.strip():
        long_term_block = "长期会话摘要（供参考）：\n" + long_term_summary.strip() + "\n\n"

    return history_block, long_term_block


def _zero_citation_stats() -> Dict[str, int]:
    return {"jec_qa": 0, "cail2018": 0, "total": 0}


def _make_citation(doc, idx: int) -> Dict[str, Any]:
    md = doc.metadata or {}
    snippet = clean_evidence_text(doc.page_content or "").strip()
    if len(snippet) > _CITATION_SNIPPET_MAX:
        snippet = snippet[:_CITATION_SNIPPET_MAX] + "..."
    return {
        "index": idx,
        "dataset": md.get("dataset"),
        "split": md.get("split"),
        "id": md.get("id"),
        "subject": md.get("subject"),
        "legal_domain": md.get("legal_domain"),
        "snippet": snippet,
    }


# ──────────────────────── 路由节点 ────────────────────────

def _route_classify(state: Dict[str, Any]) -> Dict[str, Any]:
    question = (state.get("question") or "").strip()
    trace = list(state.get("chain_trace") or [])
    trace.append("步骤1：识别问题意图（chain:intent_route）")

    source_mode = (state.get("source_mode") or "auto").strip().lower()
    if source_mode not in ("auto", "balanced", "jec_only", "cail_only"):
        source_mode = "auto"
    resolved = resolve_source_mode(source_mode, question)

    intent_info = llm_intent_route(question, chat_history=state.get("chat_history"), trace=trace)
    return {
        **state,
        "question": question,
        "source_mode": source_mode,
        "resolved_source_mode": resolved,
        "is_legal": intent_info.get("intent") == "legal",
        "intent": intent_info.get("intent", "non_legal"),
        "intent_info": intent_info,
        "chain_trace": trace,
    }


# ──────────────────────── 分支节点 ────────────────────────

def _node_empty(state: Dict[str, Any]) -> Dict[str, Any]:
    tr = list(state.get("chain_trace") or [])
    tr.append("提示：问题为空，请输入内容（chain:empty_question）")
    return {
        "answer": "请输入你的问题。",
        "citations": [],
        "contexts": [],
        "chain_trace": tr,
        "effective_source_mode": None,
        "citation_stats": _zero_citation_stats(),
    }


def _node_non_legal_direct(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    非法律问题：通用大模型直接回答，不检索知识库，不拼接「知识库覆盖」小结。
    """
    question = state.get("question", "")
    intent_info = state.get("intent_info") or {}
    tr = list(state.get("chain_trace") or [])
    reason = intent_info.get("route_reason") or ""
    tr.append(
        "步骤2：判定为非法律问题，使用通用助手直接回答（不检索知识库）"
        + (f" — 理由：{reason}" if reason else "")
        + "（chain:non_legal_direct）"
    )
    answer = answer_non_legal(
        question,
        chat_history=state.get("chat_history"),
        long_term_summary=state.get("long_term_summary"),
    )
    return {
        "answer": answer,
        "citations": [],
        "contexts": [],
        "chain_trace": tr,
        "effective_source_mode": None,
        "citation_stats": _zero_citation_stats(),
        "intent": "non_legal",
        "intent_info": intent_info,
        "skipped_retrieval": True,
    }


def _build_legal_system_prompt(
    legal_domain_label: Optional[str],
    coverage: str,
    allow_common_sense: bool,
) -> str:
    domain_line = (
        f"当前用户选择的法律领域为「{legal_domain_label}」，请优先基于该领域内的检索证据作答。\n"
        if legal_domain_label else ""
    )
    coverage_hint = {
        "full": "本次检索命中了多条相关证据，请以这些证据为主要依据作答。",
        "partial": "本次检索只命中了有限/部分相关的证据，可结合通用法律常识补充，但须按规则区分标注。",
        "none": "本次检索未命中直接相关的证据，请主要基于通用法律常识谨慎作答，并提示用户该结论的不确定性。",
    }.get(coverage, "")

    if allow_common_sense:
        rules = (
            "硬性输出规则（务必遵守）：\n"
            "1) 若某句结论由某条检索证据支持，必须在句末标注「证据[i]」（i 为证据编号），可标注多条如「证据[1][3]」。\n"
            "2) 若某句来自通用法律常识或推理补全（不是上述检索证据原文支持），必须在句末标注「（通用知识，非知识库证据）」。\n"
            "3) 不得虚构具体法条编号、判例文号或条文原文；涉及具体条文必须来自检索证据，否则改为一般性描述并标注「（通用知识，非知识库证据）」。\n"
            "4) 允许你使用通用法律常识进行必要的解释和扩展，不必死板地只复述证据。但标注规则不得省略。\n"
            "5) 若证据与问题相关性较弱或完全无关，请坦诚说明，并主要基于通用知识回答。\n"
        )
    else:
        rules = (
            "硬性输出规则（务必遵守）：\n"
            "1) 仅基于检索证据作答。若某句结论由某条检索证据支持，必须在句末标注「证据[i]」。\n"
            "2) 不得虚构法条或事实；证据不足时请明确说明，并建议用户补充哪些信息。\n"
        )
    return (
        "你是法律领域助手。"
        + domain_line
        + "你将收到用户问题、一段可选的「证据关系分析」，以及多条编号的「检索证据」。\n"
        + (coverage_hint + "\n" if coverage_hint else "")
        + rules
        + "输出要简洁、专业、可执行。"
    )


def _build_legal_user_prompt(
    question: str,
    history_block: str,
    long_term_block: str,
    bridge_context: str,
    evidence_labels: List[str],
    contexts: List[str],
) -> str:
    if not contexts:
        return (
            long_term_block
            + f"用户问题：{question}\n"
            + history_block
            + "（本次未检索到相关证据）\n"
            + "请基于通用法律常识谨慎作答，并全程使用「（通用知识，非知识库证据）」标注，"
            + "同时提示用户补充哪些信息可提高后续检索命中率。"
        )

    bridge_block = (f"证据关系分析（由系统自动生成）：\n{bridge_context}\n\n" if bridge_context else "")
    labels_hint = ""
    if evidence_labels:
        per = [f"证据[{i+1}]={evidence_labels[i]}" for i in range(len(evidence_labels))]
        labels_hint = (
            "证据相关性标签（供参考，strong=强相关，weak=弱相关，unrelated=无关）：\n"
            + "、".join(per) + "\n\n"
        )

    return (
        long_term_block
        + f"用户问题：{question}\n"
        + history_block
        + bridge_block
        + labels_hint
        + "检索证据如下（每条以编号标注）：\n"
        + "\n\n".join(contexts)
        + "\n\n"
        + "请输出：\n"
        + "1) 结论（1-3 句）：按规则标注「证据[i]」或「（通用知识，非知识库证据）」。\n"
        + "2) 依据：对每条使用到的证据按编号展开说明；未命中证据的常识补充放在末尾并按规则标注。"
    )


def _node_legal_rag(state: Dict[str, Any]) -> Dict[str, Any]:
    question = state.get("question", "")
    chat_history = state.get("chat_history")
    long_term_summary = state.get("long_term_summary")
    top_k = state.get("top_k") or config.RETRIEVAL_TOP_K
    use_mmr = state.get("use_mmr")
    if use_mmr is None:
        use_mmr = config.RETRIEVAL_USE_MMR_DEFAULT
    use_rrf = bool(state.get("use_rrf", True))
    use_evidence_labels = bool(state.get("use_evidence_labels", True))
    force_direct_llm = bool(state.get("force_direct_llm", False))
    legal_domain_arg = state.get("legal_domain")
    intent_info: Dict[str, Any] = state.get("intent_info") or {}

    allow_common_sense = bool(intent_info.get("allow_common_sense", True))
    llm_search_queries: List[str] = list(intent_info.get("search_queries") or [])
    llm_clar_hints: List[str] = list(intent_info.get("clarification_hints") or [])
    needs_clar = bool(intent_info.get("needs_clarification", False)) or needs_clarification(question)

    history_block, long_term_block = _history_blocks(chat_history, long_term_summary)
    tr = list(state.get("chain_trace") or [])
    tr.append("步骤1：判定为法律问题，进入法律RAG检索流程（chain:legal_branch）")

    eff_mode = state.get("resolved_source_mode") or "balanced"
    ld_norm = normalize_legal_domain_for_filter(legal_domain_arg)

    if force_direct_llm:
        tr.append("步骤2：实验模式启用仅LLM直答，跳过知识库检索（chain:force_direct_llm）")
        answer = answer_non_legal(
            question,
            chat_history=chat_history,
            long_term_summary=long_term_summary,
        )
        return {
            "answer": answer,
            "citations": [],
            "contexts": [],
            "chain_trace": tr,
            "effective_source_mode": "direct_llm",
            "legal_domain": ld_norm,
            "skipped_retrieval": True,
            "citation_stats": _zero_citation_stats(),
            "intent": "legal",
            "intent_info": intent_info,
            "coverage": "none",
            "evidence_labels": [],
        }

    # ── 需要澄清：直接引导用户补充信息 ──
    if needs_clar:
        tr.append("步骤2：问题信息不足，引导用户补充细节（chain:clarify_user）")
        return {
            "answer": build_clarify_reply(question, llm_clar_hints),
            "citations": [],
            "contexts": [],
            "chain_trace": tr,
            "effective_source_mode": eff_mode,
            "legal_domain": ld_norm,
            "skipped_retrieval": True,
            "citation_stats": _zero_citation_stats(),
            "intent": "legal",
            "intent_info": intent_info,
            "coverage": "none",
            "evidence_labels": [],
        }

    # ── 关键词抽取（辅助多路检索与重排） ──
    tr.append("步骤2：提取查询关键词（chain:keyword_extraction）")
    query_keywords = extract_query_keywords(question, tr)

    # ── 检索 ──
    tr.append(
        "步骤3：在向量知识库中检索相关证据"
        + (f"（LLM 建议查询：{llm_search_queries}）" if llm_search_queries else "")
        + "（chain:vector_retrieve）"
    )
    try:
        vector_store = get_chroma_vector_store()
        retrieved_docs = retrieve_with_multi_queries(
            vector_store,
            question,
            llm_search_queries,
            top_k,
            eff_mode,
            use_mmr,
            use_rrf,
            legal_domain_arg,
            query_keywords,
            tr,
        )
    except Exception as e:
        tr.append("步骤3：向量库检索失败（chain:retrieve_error）")
        return {
            "answer": f"向量库或嵌入初始化失败：{e}",
            "citations": [],
            "contexts": [],
            "chain_trace": tr,
            "effective_source_mode": eff_mode,
            "legal_domain": ld_norm,
            "citation_stats": _zero_citation_stats(),
            "intent": "legal",
            "intent_info": intent_info,
            "coverage": "none",
            "evidence_labels": [],
        }

    contexts: List[str] = [format_context(d, i + 1) for i, d in enumerate(retrieved_docs)]
    citations: List[Dict[str, Any]] = [_make_citation(d, i + 1) for i, d in enumerate(retrieved_docs)]

    # ── 证据相关性评估（可用于消融） ──
    evidence_labels: List[str] = []
    coverage: str = "none"
    if use_evidence_labels:
        tr.append("步骤4：评估检索证据相关性（chain:evidence_relevance_score）")
        relevance = score_evidence_relevance(question, retrieved_docs, tr)
        evidence_labels = list(relevance.get("labels") or [])
        coverage = str(relevance.get("coverage") or "none")
        for idx, c in enumerate(citations):
            if idx < len(evidence_labels):
                c["relevance"] = evidence_labels[idx]
    else:
        tr.append("步骤4：实验模式关闭证据相关性标注（ablation:no_evidence_label）")
        coverage = "partial" if citations else "none"

    # ── 桥接摘要（仅在有相关证据时） ──
    bridge_context = ""
    if coverage != "none":
        tr.append("步骤5：分析多条证据之间的逻辑关系（chain:bridge_context）")
        bridge_context = generate_bridge_context(question, contexts, tr)

    # ── 生成 ──
    tr.append("步骤6：综合证据与通用法律常识，调用大模型生成回答（chain:llm_generate_answer）")
    domain_label = LEGAL_DOMAIN_LABELS.get(ld_norm, ld_norm) if ld_norm else None
    system_prompt = _build_legal_system_prompt(domain_label, coverage, allow_common_sense)
    user_prompt = _build_legal_user_prompt(
        question, history_block, long_term_block, bridge_context, evidence_labels, contexts
    )
    try:
        answer = call_llm(system_prompt, user_prompt)
    except Exception as e:
        answer = str(e)

    jec_n = sum(1 for c in citations if c.get("dataset") == config.DATASET_JEC_QA)
    cail_n = sum(1 for c in citations if c.get("dataset") == config.DATASET_CAIL2018)

    return {
        "answer": answer,
        "citations": citations,
        "contexts": contexts,
        "query_keywords": query_keywords,
        "bridge_context": bridge_context,
        "chain_trace": tr,
        "effective_source_mode": eff_mode,
        "legal_domain": ld_norm,
        "citation_stats": {"jec_qa": jec_n, "cail2018": cail_n, "total": len(citations)},
        "intent": "legal",
        "intent_info": intent_info,
        "coverage": coverage,
        "evidence_labels": evidence_labels,
    }


# ──────────────────────── LCEL Chain ────────────────────────

_rag_branch = RunnableBranch(
    (lambda s: not (s.get("question") or "").strip(), RunnableLambda(_node_empty)),
    (lambda s: not s.get("is_legal", False), RunnableLambda(_node_non_legal_direct)),
    RunnableLambda(_node_legal_rag),
)

rag_chain = RunnableLambda(_route_classify) | _rag_branch


# ──────────────────────── UI 结果收尾 ────────────────────────

def _build_kb_coverage_banner(
    coverage: str,
    evidence_labels: List[str],
    n_citations: int,
    search_queries: List[str],
) -> str:
    """
    法律分支的「知识库覆盖」小结：强制追加在回答末尾，保证每次法律问答都明示
    知识库的参与情况。非法律分支不调用本函数。
    """
    n_strong = sum(1 for x in evidence_labels if x == "strong")
    n_weak = sum(1 for x in evidence_labels if x == "weak")
    if coverage == "full":
        return (
            f"\n\n> **知识库覆盖**：命中 {n_strong} 条强相关证据"
            f"（共检索到 {n_citations} 条），回答以知识库证据为主要依据。"
        )
    if coverage == "partial":
        hit = n_strong + n_weak
        return (
            f"\n\n> **知识库覆盖**：命中 {hit} 条相关证据"
            f"（其中强相关 {n_strong} 条、弱相关 {n_weak} 条，共检索 {n_citations} 条），"
            f"其余内容为通用法律常识补充（已按规则标注）。"
        )
    q_hint = ""
    if search_queries:
        q_hint = f"（已尝试检索：{ '、'.join(q[:30] for q in search_queries[:3]) }）"
    return (
        f"\n\n> **知识库覆盖**：本次检索未在知识库中找到直接相关的条目"
        f"{q_hint}。以下回答以通用法律常识为主，请谨慎采用。"
    )


def _build_retrieval_summary(
    result: Dict[str, Any],
    prefs: Dict[str, Any],
    top_k: int,
    elapsed_sec: float,
    mode: str,
) -> Dict[str, Any]:
    ld = result.get("legal_domain")
    trace = result.get("chain_trace") or []
    vec_ran = any(t == "chain:vector_retrieve" for t in trace) or (mode == "agent")
    qk = result.get("query_keywords") or {}
    intent_info = result.get("intent_info") or {}
    intent = result.get("intent") or intent_info.get("intent") or ""
    return {
        "mode": mode,
        "elapsed_sec": round(elapsed_sec, 2),
        "top_k": top_k,
        "intent": intent,
        "intent_route": {
            "intent": intent,
            "routed_by": intent_info.get("routed_by") or "",
            "route_reason": intent_info.get("route_reason") or "",
            "search_queries": list(intent_info.get("search_queries") or []),
            "needs_clarification": bool(intent_info.get("needs_clarification", False)),
            "allow_common_sense": bool(intent_info.get("allow_common_sense", True)),
        },
        "query_analysis": {
            "specific_terms": list(qk.get("specific_terms") or []),
            "broad_topics": list(qk.get("broad_topics") or []),
            "query_type": qk.get("query_type") or "",
        },
        "bridge_context": result.get("bridge_context") or "",
        "runtime_prefs": {
            "source_mode": prefs.get("source_mode"),
            "use_mmr": bool(prefs.get("use_mmr")),
            "use_rrf": bool(prefs.get("use_rrf", True)),
            "use_evidence_labels": bool(prefs.get("use_evidence_labels", True)),
            "use_agent_default": bool(prefs.get("use_agent_default")),
            "force_direct_llm": bool(prefs.get("force_direct_llm", False)),
            "enable_agent_fallback": bool(prefs.get("enable_agent_fallback", True)),
            "active_experiment_preset": prefs.get("active_experiment_preset", ""),
        },
        "effective_source_mode": result.get("effective_source_mode"),
        "legal_domain_code": ld or "",
        "legal_domain_label": (LEGAL_DOMAIN_LABELS.get(ld, ld) if ld else "综合（未按领域过滤）"),
        "citation_stats": result.get("citation_stats") or _zero_citation_stats(),
        "skipped_retrieval": bool(result.get("skipped_retrieval")),
        "vector_retrieval_ran": vec_ran,
        "evidence_count": len(result.get("citations") or []),
        "coverage": result.get("coverage") or ("none" if intent == "legal" else ""),
        "evidence_labels": list(result.get("evidence_labels") or []),
    }


def _finalize_rag_ui_result(
    result: Dict[str, Any],
    prefs: Dict[str, Any],
    top_k: int,
    elapsed_sec: float,
    mode: str,
) -> Dict[str, Any]:
    out = dict(result)
    intent_info = out.get("intent_info") or {}
    intent = out.get("intent") or intent_info.get("intent") or ""

    # 非法律分支：不追加任何尾注
    if intent == "non_legal":
        out["retrieval_summary"] = _build_retrieval_summary(out, prefs, top_k, elapsed_sec, mode)
        return out

    # 法律分支 / Agent 模式：强制追加「知识库覆盖」小结
    cites = out.get("citations") or []
    coverage = str(out.get("coverage") or ("none" if not cites else "partial"))
    evidence_labels = list(out.get("evidence_labels") or [])
    search_queries = list(intent_info.get("search_queries") or [])
    out["answer"] = (out.get("answer") or "").rstrip() + _build_kb_coverage_banner(
        coverage, evidence_labels, len(cites), search_queries
    )

    out["retrieval_summary"] = _build_retrieval_summary(out, prefs, top_k, elapsed_sec, mode)
    if mode == "agent" and not cites:
        summ = dict(out["retrieval_summary"])
        summ["note"] = (
            "Agent 模式：证据由工具在对话中返回，结构化 citations 可能为空；"
            "链式追踪见「展示 RAG 痕迹」中的链式追踪。"
        )
        out["retrieval_summary"] = summ
    return out


# ──────────────────────── 对外入口 ────────────────────────

def answer_question(
    question: str,
    chat_history: Optional[List[Tuple[str, str]]] = None,
    top_k: Optional[int] = None,
    long_term_summary: Optional[str] = None,
    legal_domain: Optional[str] = None,
    runtime_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    统一入口。检索策略（source_mode / MMR / 是否走 Agent）来自 runtime_rag_prefs.json。
    """
    prefs = load_rag_prefs()
    if runtime_overrides:
        merged = dict(prefs)
        merged.update(runtime_overrides)
        prefs = merged

    source_mode = str(prefs.get("source_mode") or "balanced")
    use_mmr = bool(prefs.get("use_mmr", False))
    use_rrf = bool(prefs.get("use_rrf", True))
    use_evidence_labels = bool(prefs.get("use_evidence_labels", True))
    use_agent = bool(prefs.get("use_agent_default", False))
    force_direct_llm = bool(prefs.get("force_direct_llm", False))
    enable_agent_fallback = bool(prefs.get("enable_agent_fallback", True))
    top_k = top_k or config.RETRIEVAL_TOP_K

    if use_agent:
        try:
            from rag_agent import answer_with_agent

            t0 = time.perf_counter()
            out = answer_with_agent(
                question=question,
                chat_history=chat_history,
                long_term_summary=long_term_summary,
                source_mode=source_mode,
                use_mmr=use_mmr,
                legal_domain=legal_domain or "",
                enable_fallback=enable_agent_fallback,
            )
            elapsed = time.perf_counter() - t0
            out.setdefault("citations", [])
            return _finalize_rag_ui_result(out, prefs, top_k, elapsed, "agent")
        except Exception as e:
            err_out: Dict[str, Any] = {
                "answer": f"Agent 模式不可用，已提示错误：{e}",
                "citations": [],
                "contexts": [],
                "chain_trace": ["agent_import_or_run_failed"],
                "effective_source_mode": None,
                "legal_domain": normalize_legal_domain_for_filter(legal_domain),
                "citation_stats": _zero_citation_stats(),
            }
            return _finalize_rag_ui_result(err_out, prefs, top_k, 0.0, "agent")

    state: Dict[str, Any] = {
        "question": question,
        "chat_history": chat_history or [],
        "top_k": top_k,
        "long_term_summary": long_term_summary,
        "source_mode": source_mode,
        "use_mmr": use_mmr,
        "use_rrf": use_rrf,
        "use_evidence_labels": use_evidence_labels,
        "force_direct_llm": force_direct_llm,
        "legal_domain": legal_domain,
        "chain_trace": [],
    }
    t0 = time.perf_counter()
    out = rag_chain.invoke(state)
    elapsed = time.perf_counter() - t0
    return _finalize_rag_ui_result(out, prefs, top_k, elapsed, "lcel")
