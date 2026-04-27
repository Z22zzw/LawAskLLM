"""
Tool-calling Agent：与 rag_service.rag_chain 并存的 Agent 执行路径。
由 rag_prefs.use_agent_default 控制是否默认启用；rag_service.answer_question 会在需要时调用本模块。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import config
from langchain_core.tools import tool
from legal_domain_map import normalize_legal_domain_for_filter
from rag_llm import answer_non_legal, llm_intent_route
from rag_prefs import load_rag_prefs
from rag_stream_callbacks import emit_trace_step


def _agent_tr(trace: List[str], msg: str) -> None:
    trace.append(msg)
    emit_trace_step(msg)


def _zero_citation_stats() -> Dict[str, int]:
    return {"jec_qa": 0, "cail2018": 0, "total": 0}


# ──────────────────────── 工具：知识库检索 ────────────────────────

@tool
def search_legal_kb(query: str, legal_domain: str = "", dataset: str = "balanced") -> str:
    """检索法律向量知识库。legal_domain：与对话选择的领域一致，如 xingfa；综合则留空。dataset：jec-qa / cail2018 / balanced / auto。"""
    from rag_retrieval import retrieve_documents
    from vector_store_service import get_chroma_vector_store

    mode_map = {
        "jec-qa": "jec_only",
        "cail2018": "cail_only",
        "balanced": "balanced",
        "auto": "auto",
    }
    key = (dataset or "balanced").strip().lower().replace("_", "-")
    mode = mode_map.get(key, "balanced")
    prefs = load_rag_prefs()
    use_mmr = bool(prefs.get("use_mmr", False))
    use_rrf = bool(prefs.get("use_rrf", True))
    vs = get_chroma_vector_store()
    trace: List[str] = []
    ld = legal_domain.strip() or None
    docs = retrieve_documents(
        vs,
        query,
        config.RETRIEVAL_TOP_K,
        mode,
        use_mmr,
        use_rrf=use_rrf,
        trace=trace,
        legal_domain=ld,
    )
    if not docs:
        return "（未检索到相关片段；可换关键词、调整 legal_domain 或 dataset。）"
    parts: List[str] = []
    for i, d in enumerate(docs, 1):
        body = (d.page_content or "")[:900]
        ds = (d.metadata or {}).get("dataset", "")
        dom = (d.metadata or {}).get("legal_domain", "")
        parts.append(f"[{i}] 来源:{ds} 领域:{dom}\n{body}")
    return "\n\n---\n\n".join(parts)


# ──────────────────────── 辅助构造返回 ────────────────────────

def _error_result(
    msg: str, trace_tag: str, legal_domain: str, extra: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    emit_trace_step(trace_tag)
    out: Dict[str, Any] = {
        "answer": msg,
        "citations": [],
        "contexts": [],
        "chain_trace": [trace_tag],
        "effective_source_mode": None,
        "legal_domain": normalize_legal_domain_for_filter(legal_domain),
        "citation_stats": _zero_citation_stats(),
    }
    if extra:
        out.update(extra)
    return out


def _build_legal_agent_system_prompt(
    legal_domain: str, pref_mode: str, llm_search_queries: List[str]
) -> str:
    sqs_hint = ""
    if llm_search_queries:
        sqs_hint = (
            "路由器建议的检索查询（可作为工具调用的 query 起点，最多 3 条，必要时可自行改写）："
            + "；".join(q[:60] for q in llm_search_queries[:3]) + "。"
        )
    return (
        "你是法律领域助手。本轮已被意图路由判定为法律问题，请至少调用一次工具 search_legal_kb 检索知识库；"
        f"调用时必须传入参数：legal_domain=\"{legal_domain.strip()}\"（用户当前选择的领域代码，综合则为空字符串），"
        "dataset 可取 jec-qa / cail2018 / balanced / auto。"
        + sqs_hint + "\n"
        + "再根据检索结果用中文作答。\n"
        + "硬性输出规则：\n"
        + "1) 若某句结论由某条检索证据支持，必须在句末标注「证据[i]」（i 为证据编号）。\n"
        + "2) 若某句来自通用法律常识或推理补全，必须在句末标注「（通用知识，非知识库证据）」。\n"
        + "3) 不得虚构具体法条编号、判例文号或条文原文；涉及具体条文必须来自检索证据。\n"
        + "4) 若工具返回「未检索到相关片段」，应坦诚说明未命中，再以通用法律常识谨慎作答，并全程加上「（通用知识，非知识库证据）」标注。\n"
        + f"知识源策略偏好：{pref_mode}。"
    )


def _extract_agent_text(msgs: List[Any]) -> str:
    from langchain_core.messages import AIMessage

    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            c = m.content
            if isinstance(c, str) and c.strip():
                return c.strip()
            if isinstance(c, list):
                parts = [getattr(x, "text", str(x)) for x in c]
                joined = "\n".join(parts).strip()
                if joined:
                    return joined
    if msgs:
        return (getattr(msgs[-1], "content", None) or str(msgs[-1])).strip()
    return ""


# ──────────────────────── 主入口 ────────────────────────

def answer_with_agent(
    question: str,
    chat_history: Optional[List[Tuple[str, str]]] = None,
    long_term_summary: Optional[str] = None,
    source_mode: str = "auto",
    use_mmr: bool = False,
    legal_domain: str = "",
    enable_fallback: bool = True,
) -> Dict[str, Any]:
    trace: List[str] = []
    _agent_tr(trace, "agent:start")

    if not (question or "").strip():
        return _error_result("请输入你的问题。", "agent:empty", legal_domain)
    if not config.LLM_API_KEY:
        return _error_result("LLM_API_KEY 未配置，无法运行 Agent。", "agent:no_llm", legal_domain)

    # 意图路由：与 LCEL 分支保持一致
    intent_info = llm_intent_route(question, chat_history=chat_history, trace=trace)
    intent = intent_info.get("intent", "legal")

    # 非法律：直接用 LLM 作答，不进 agent graph
    if intent == "non_legal":
        _agent_tr(trace, "agent:non_legal_direct（非法律问题，不进 agent graph，直接由 LLM 作答）")
        answer = answer_non_legal(question, chat_history=chat_history, long_term_summary=long_term_summary)
        return {
            "answer": answer,
            "citations": [],
            "contexts": [],
            "chain_trace": trace,
            "effective_source_mode": None,
            "legal_domain": normalize_legal_domain_for_filter(legal_domain),
            "citation_stats": _zero_citation_stats(),
            "intent": "non_legal",
            "intent_info": intent_info,
            "skipped_retrieval": True,
        }

    # 法律：走 agent graph
    try:
        from langchain.agents import create_agent
        from langchain_core.messages import HumanMessage
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        _agent_tr(trace, "agent:import_fallback")
        if not enable_fallback:
            return _error_result(
                f"Agent 依赖加载失败，且当前实验关闭了回退机制：{e}",
                "agent:fallback_disabled",
                legal_domain,
                {"intent": "legal", "intent_info": intent_info},
            )
        return _fallback_lcel(
            question, chat_history, long_term_summary, source_mode, use_mmr, legal_domain, trace, str(e)
        )

    llm = ChatOpenAI(
        model=config.LLM_MODEL or "deepseek-v3.2",
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY,
        temperature=0.2,
    )
    pref = source_mode or "auto"
    system_prompt = _build_legal_agent_system_prompt(
        legal_domain, pref, list(intent_info.get("search_queries") or [])
    )
    try:
        agent_graph = create_agent(model=llm, tools=[search_legal_kb], system_prompt=system_prompt)
    except Exception as e:
        _agent_tr(trace, "agent:create_agent_failed")
        if not enable_fallback:
            return _error_result(
                f"Agent 创建失败，且当前实验关闭了回退机制：{e}",
                "agent:fallback_disabled",
                legal_domain,
                {"intent": "legal", "intent_info": intent_info},
            )
        return _fallback_lcel(
            question, chat_history, long_term_summary, source_mode, use_mmr, legal_domain, trace, str(e)
        )

    hist = ""
    if chat_history:
        for u, a in chat_history[-3:]:
            hist += f"用户：{u}\n助手：{(a or '')[:180]}\n"
    summ = f"[长期摘要]{long_term_summary[:400]}\n" if long_term_summary else ""
    ld_display = legal_domain.strip() or "（综合）"
    user_block = f"{summ}{hist}当前法律领域：{ld_display}\n当前问题：{question.strip()}"

    try:
        result = agent_graph.invoke({"messages": [HumanMessage(content=user_block)]})
        _agent_tr(trace, "agent:graph_done")
        out_text = _extract_agent_text(result.get("messages") or [])
        return {
            "answer": out_text or "（Agent 未返回文本）",
            "citations": [],
            "contexts": [],
            "chain_trace": trace,
            "effective_source_mode": pref,
            "legal_domain": normalize_legal_domain_for_filter(legal_domain),
            "citation_stats": _zero_citation_stats(),
            "intent": "legal",
            "intent_info": intent_info,
            # Agent 模式下 citations 为空时，coverage 视为 none，由 finalize 追加"未命中"小结
            "coverage": "none",
            "evidence_labels": [],
        }
    except Exception as e:
        _agent_tr(trace, "agent:graph_error")
        if not enable_fallback:
            return _error_result(
                f"Agent 执行失败，且当前实验关闭了回退机制：{e}",
                "agent:fallback_disabled",
                legal_domain,
                {"intent": "legal", "intent_info": intent_info},
            )
        return _fallback_lcel(
            question, chat_history, long_term_summary, source_mode, use_mmr, legal_domain, trace, str(e)
        )


def _fallback_lcel(
    question: str,
    chat_history: Optional[List[Tuple[str, str]]],
    long_term_summary: Optional[str],
    source_mode: str,
    use_mmr: bool,
    legal_domain: str,
    trace: List[str],
    err: str,
) -> Dict[str, Any]:
    import rag_service as rs

    _agent_tr(trace, f"agent:fallback_lcel:{err[:120]}")
    state: Dict[str, Any] = {
        "question": question,
        "chat_history": chat_history or [],
        "top_k": config.RETRIEVAL_TOP_K,
        "long_term_summary": long_term_summary,
        "source_mode": source_mode,
        "use_mmr": use_mmr,
        "legal_domain": legal_domain,
        "chain_trace": trace,
    }
    out = rs.rag_chain.invoke(state)
    out["chain_trace"] = list(out.get("chain_trace") or []) + trace
    out["answer"] = (f"[Agent 不可用，已自动改用 LCEL 链式 RAG] {out.get('answer', '')}").strip()
    return out
