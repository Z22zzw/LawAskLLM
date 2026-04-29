"""
LLM 语义处理层：
- 意图路由（legal / non_legal） + 检索查询建议 + 澄清提示
- 查询关键词抽取（specific_terms / broad_topics / query_type）
- 证据相关性评估（strong / weak / unrelated + coverage）
- 证据桥接摘要
- 非法律问题直答
- 会话长期摘要

所有函数在 LLM 失败时均有健壮降级（关键词规则或静默跳过）。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core import config
from app.rag.llm_client import call_llm, call_llm_stream
from app.rag.stream_callbacks import answer_streaming_enabled, emit_answer_token, emit_trace_step


# ──────────────────────── 关键词兜底规则 ────────────────────────

def _llm_tr(trace: List[str], msg: str) -> None:
    trace.append(msg)
    emit_trace_step(msg)


_LEGAL_KEYWORDS = (
    "法律", "法规", "条文", "判决", "判处", "裁定", "罪名", "犯罪",
    "刑法", "民法", "行政", "起诉", "被告", "原告", "管辖", "时效",
    "证据", "合同", "侵权", "赔偿", "律师", "法院", "检察院", "审判",
    "刑事", "民事", "行政诉讼", "刑事诉讼", "盗窃", "抢劫", "故意伤害",
)


def looks_like_legal_question(question: str) -> bool:
    """LLM 路由失败时的关键词兜底。"""
    q = (question or "").strip()
    if not q:
        return False
    if any(k in q for k in _LEGAL_KEYWORDS):
        return True
    if "是什么罪" in q or "罪名" in q:
        return True
    q_lower = q.lower()
    if "criminal" in q_lower or "charge" in q_lower:
        return True
    return False


def needs_clarification(question: str) -> bool:
    """基于长度/关键词的兜底澄清判断。"""
    t = (question or "").strip()
    if len(t) < 10:
        return True
    if len(t) < 28 and "？" not in t and "?" not in t:
        if not any(w in t for w in ("罪", "法", "条", "如何", "是否", "能否", "怎么", "哪")):
            return True
    return False


def default_clarify_reply(question: str) -> str:
    return (
        "您的问题可能还不够具体，我先帮您梳理一下。请尽量补充后再问一遍，以便检索知识库：\n\n"
        "1. **场景**：涉及民事、刑事还是行政？是否有大致时间、地点？\n"
        "2. **主体**：当事人身份（自然人/公司）、与您的关系？\n"
        "3. **诉求**：您想判断的是罪名、责任、程序，还是某道选择题的考点？\n\n"
        f"（当前输入：{question.strip()[:80]}{'…' if len(question.strip()) > 80 else ''}）"
    )


def build_clarify_reply(question: str, hints: List[str]) -> str:
    """有 LLM 提供的 hints 时优先用 hints 版本。"""
    hints = [h for h in (hints or []) if h and str(h).strip()]
    if not hints:
        return default_clarify_reply(question)
    hints_md = "\n".join(f"- {h}" for h in hints)
    q = (question or "").strip()
    return (
        "为了在知识库中检索到更有针对性的依据，请补充以下信息后再问一遍：\n\n"
        + hints_md
        + f"\n\n（当前输入：{q[:80]}{'…' if len(q) > 80 else ''}）"
    )


# ──────────────────────── JSON 解析工具 ────────────────────────

def _safe_json(raw: str) -> Any:
    """去掉 ```json ... ``` 包裹后 json.loads。"""
    cleaned = re.sub(r"```json?\s*", "", raw or "")
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    return json.loads(cleaned)


def _history_tail_lines(chat_history: Optional[List[Tuple[str, str]]], n: int, trunc: int) -> str:
    if not chat_history:
        return ""
    tail = chat_history[-n:]
    lines: List[str] = []
    for u, a in tail:
        lines.append(f"用户：{u}")
        lines.append(f"助手：{(a or '')[:trunc]}")
    return "\n".join(lines)


# ──────────────────────── 意图路由 ────────────────────────

def llm_intent_route(
    question: str,
    chat_history: Optional[List[Tuple[str, str]]] = None,
    trace: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    通用大模型前置意图判断。返回：
      - intent: "legal" | "non_legal"
      - needs_clarification: bool
      - clarification_hints: List[str]
      - search_queries: List[str]
      - allow_common_sense: bool
      - route_reason: str
      - routed_by: "llm" | "fallback_keyword"
    """
    trace = trace if trace is not None else []
    q = (question or "").strip()

    fallback: Dict[str, Any] = {
        "intent": "legal" if looks_like_legal_question(q) else "non_legal",
        "needs_clarification": needs_clarification(q) if q else False,
        "clarification_hints": [],
        "search_queries": [q] if q else [],
        "allow_common_sense": True,
        "route_reason": "",
        "routed_by": "fallback_keyword",
    }
    if not config.LLM_API_KEY or not q:
        _llm_tr(trace, "步骤0：LLM 未配置或问题为空，使用关键词回退路由（intent_route:fallback）")
        return fallback

    system_prompt = (
        "你是一个法律问答系统的路由助手。对用户问题做二元意图判断，并给出检索计划。\n"
        "判定规则：\n"
        "- 只要问题涉及法律条文、罪名、诉讼程序、案件事实的法律分析、"
        "法考/司考题目、合同/侵权/刑事/民事/行政等任何法律议题，intent=legal。\n"
        "- 问候、闲聊、系统使用说明、与法律无关的通用知识问答，intent=non_legal。\n"
        "- 若用户描述过于模糊导致无法进行法律分析（例如\"我有个官司\"没有任何细节），"
        "把 needs_clarification 设为 true 并给出 1-3 条需要补充的信息点。\n"
        "- 仅当 intent=legal 时生成 search_queries（1-3 条，用于向量检索法律知识库），"
        "每条应是精炼的查询串（法律术语/罪名/法条关键词）。intent=non_legal 时 search_queries 返回空数组。\n"
        "- allow_common_sense 默认为 true（允许结合通用法律常识补全回答）。\n"
        "严格输出 JSON，不要解释、不要 Markdown 代码块标记。"
    )
    hist = _history_tail_lines(chat_history, 2, 120)
    hist_block = (f"最近对话（仅供参考）：\n{hist}\n\n" if hist else "")
    user_prompt = (
        hist_block
        + f"用户当前问题：{q[:300]}\n\n"
        '请输出 JSON，字段如下：\n'
        '{"intent": "legal"|"non_legal", '
        '"needs_clarification": true|false, '
        '"clarification_hints": ["补充点1"], '
        '"search_queries": ["查询串1", "查询串2"], '
        '"allow_common_sense": true|false, '
        '"route_reason": "一句话理由"}'
    )
    try:
        parsed = _safe_json(call_llm(system_prompt, user_prompt))

        intent = str(parsed.get("intent") or "").strip().lower()
        if intent not in ("legal", "non_legal"):
            intent = fallback["intent"]

        needs_clar = bool(parsed.get("needs_clarification", False))
        hints = parsed.get("clarification_hints") or []
        if not isinstance(hints, list):
            hints = []
        hints = [str(x).strip() for x in hints if str(x).strip()][:3]

        sqs = parsed.get("search_queries") or []
        if not isinstance(sqs, list):
            sqs = []
        sqs = [str(x).strip() for x in sqs if str(x).strip()][:3]
        if intent == "legal" and not sqs:
            sqs = [q]
        if intent == "non_legal":
            sqs = []

        allow_cs = parsed.get("allow_common_sense")
        allow_cs = True if allow_cs is None else bool(allow_cs)

        reason = str(parsed.get("route_reason") or "").strip()[:120]

        _llm_tr(
            trace,
            f"步骤0：LLM 意图判断 —— intent={intent}，需澄清={needs_clar}，"
            f"检索查询={sqs}，允许常识={allow_cs}，理由：{reason or '（无）'}（intent_route:llm）",
        )
        return {
            "intent": intent,
            "needs_clarification": needs_clar,
            "clarification_hints": hints,
            "search_queries": sqs,
            "allow_common_sense": allow_cs,
            "route_reason": reason,
            "routed_by": "llm",
        }
    except Exception:
        _llm_tr(trace, "步骤0：LLM 意图判断失败，回退到关键词路由（intent_route:fallback）")
        return fallback


# ──────────────────────── 关键词抽取 ────────────────────────

def _empty_keywords() -> Dict[str, Any]:
    return {"specific_terms": [], "broad_topics": [], "query_type": ""}


def extract_query_keywords(question: str, trace: List[str]) -> Dict[str, Any]:
    """
    抽取 specific_terms / broad_topics / query_type，供后续多路检索与重排使用。
    """
    if not config.LLM_API_KEY or not (question or "").strip():
        return _empty_keywords()

    system_prompt = (
        "你是法律信息抽取助手。请从用户的法律问题中提取：\n"
        "1. specific_terms：具体的法律术语、罪名、法条名、当事人角色等精确实体（2-6个）\n"
        "2. broad_topics：宏观的法律主题、部门法类别、法律原则等抽象概念（1-3个）\n"
        "3. query_type：问题类型，只能从以下四类中选一项：概念解释 / 案例分析 / 法条适用 / 对比辨析\n"
        "严格以 JSON 格式输出，不要输出其他内容。"
    )
    user_prompt = (
        f"用户问题：{question.strip()[:200]}\n\n"
        '输出格式：{"specific_terms": ["术语1", "术语2"], "broad_topics": ["主题1"], "query_type": "概念解释"}'
    )
    try:
        parsed = _safe_json(call_llm(system_prompt, user_prompt))
        specific = parsed.get("specific_terms") or []
        broad = parsed.get("broad_topics") or []
        specific = [str(x).strip() for x in specific if isinstance(specific, list) and str(x).strip()][:6]
        broad = [str(x).strip() for x in broad if isinstance(broad, list) and str(x).strip()][:3]
        qt = (parsed.get("query_type") or "").strip()
        if qt not in ("概念解释", "案例分析", "法条适用", "对比辨析"):
            qt = ""
        _llm_tr(
            trace,
            f"步骤2：提取关键词完成 —— 具体术语：{specific}；宏观主题：{broad}；"
            f"问题类型：{qt or '未识别'}（keywords:extracted）",
        )
        return {"specific_terms": specific, "broad_topics": broad, "query_type": qt}
    except Exception:
        _llm_tr(trace, "步骤2：关键词提取失败，回退到原始语义检索（keywords:fallback）")
        return _empty_keywords()


# ──────────────────────── 证据相关性评估 ────────────────────────

def _coverage_from_labels(labels: List[str]) -> str:
    n_strong = sum(1 for x in labels if x == "strong")
    n_weak = sum(1 for x in labels if x == "weak")
    if n_strong >= 2:
        return "full"
    if n_strong >= 1 or n_weak >= 2:
        return "partial"
    return "none"


def _score_by_keyword(question: str, docs: List) -> List[str]:
    q_tokens = [t for t in re.split(r"[\s，。,.；;、：:]+", (question or "").lower()) if len(t) >= 2]
    labels: List[str] = []
    for d in docs:
        body = (getattr(d, "page_content", "") or "").lower()
        subj = ((getattr(d, "metadata", None) or {}).get("subject") or "").lower()
        text = body + " " + subj
        hits = sum(1 for t in q_tokens if t in text)
        if hits >= 3:
            labels.append("strong")
        elif hits >= 1:
            labels.append("weak")
        else:
            labels.append("unrelated")
    return labels


def score_evidence_relevance(
    question: str,
    docs: List,
    trace: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    对检索证据打 strong/weak/unrelated 并汇总 coverage。
    LLM 失败时用关键词命中数兜底。
    """
    trace = trace if trace is not None else []
    if not docs:
        return {"labels": [], "coverage": "none", "scored_by": "fallback_keyword"}

    if not config.LLM_API_KEY:
        labels = _score_by_keyword(question, docs)
        return {"labels": labels, "coverage": _coverage_from_labels(labels), "scored_by": "fallback_keyword"}

    # 避免把过长的证据原文全量塞给 LLM
    from app.rag.retrieval import clean_evidence_text
    lines: List[str] = []
    for i, d in enumerate(docs, start=1):
        snippet = clean_evidence_text(getattr(d, "page_content", "") or "").strip()
        if len(snippet) > 260:
            snippet = snippet[:260] + "..."
        lines.append(f"[{i}] {snippet}")

    system_prompt = (
        "你是法律证据相关性评估员。给定用户问题与若干检索证据，"
        "为每条证据打一个标签：\n"
        "- strong：证据直接回答或显著支持该问题的核心法律要点。\n"
        "- weak：证据与问题相关但不足以直接支持结论。\n"
        "- unrelated：证据与问题几乎无关。\n"
        "严格输出 JSON：{\"labels\": [\"strong\"|\"weak\"|\"unrelated\", ...]}，"
        "labels 数组长度必须等于证据条数，顺序与证据编号一致。"
    )
    user_prompt = (
        f"用户问题：{(question or '').strip()[:200]}\n\n检索证据：\n" + "\n\n".join(lines)
    )
    try:
        parsed = _safe_json(call_llm(system_prompt, user_prompt))
        raw_labels = parsed.get("labels") or []
        if not isinstance(raw_labels, list) or len(raw_labels) != len(docs):
            raise ValueError("labels length mismatch")
        labels: List[str] = []
        for x in raw_labels:
            v = str(x).strip().lower()
            if v not in ("strong", "weak", "unrelated"):
                v = "weak"
            labels.append(v)
        _llm_tr(trace, f"步骤5：证据相关性评估完成 —— {labels}（evidence_relevance:llm）")
        return {"labels": labels, "coverage": _coverage_from_labels(labels), "scored_by": "llm"}
    except Exception:
        _llm_tr(trace, "步骤5：证据相关性评估失败，使用关键词兜底（evidence_relevance:fallback）")
        labels = _score_by_keyword(question, docs)
        return {"labels": labels, "coverage": _coverage_from_labels(labels), "scored_by": "fallback_keyword"}


# ──────────────────────── 证据桥接摘要 ────────────────────────

def generate_bridge_context(question: str, contexts: List[str], trace: List[str]) -> str:
    """
    为多条证据生成 2-3 句逻辑关系概括，帮助最终生成 LLM 理解证据关系。
    LLM 未配置或证据 < 2 条时跳过。
    """
    if not config.LLM_API_KEY or len(contexts) < 2:
        return ""
    system_prompt = (
        "你是法律证据分析助手。给定用户问题和多条检索证据，请用 2-3 句话简要概括：\n"
        "1) 这些证据分别涉及哪些法律要点；\n"
        "2) 它们之间的逻辑关系（互补、对立、递进、因果等）。\n"
        "不要复述证据原文，只概括关系。不超过 150 字。用中文输出。"
    )
    user_prompt = (
        f"用户问题：{(question or '').strip()[:200]}\n\n检索证据：\n" + "\n\n".join(contexts[:6])
    )
    try:
        bridge = call_llm(system_prompt, user_prompt).strip()
        _llm_tr(trace, "步骤5：证据关系分析完成（bridge:context_generated）")
        return bridge
    except Exception:
        _llm_tr(trace, "步骤5：证据关系分析跳过（bridge:generation_failed）")
        return ""


# ──────────────────────── 非法律问题直答 ────────────────────────

_NON_LEGAL_SYSTEM_PROMPT = (
    "你是一个通用助手，当前所在系统是一个法律知识问答平台，但本轮问题与法律无关。"
    "请直接用中文回答用户问题，简洁自然。"
    "若用户后续想咨询法律问题，可提示 TA 补充案情细节，系统会自动检索法律知识库。"
)


def answer_non_legal(
    question: str,
    chat_history: Optional[List[Tuple[str, str]]] = None,
    long_term_summary: Optional[str] = None,
) -> str:
    """
    非法律问题的通用 LLM 直答。不检索知识库。
    """
    history_text = _history_tail_lines(chat_history, 4, 200)
    history_block = (f"对话历史（仅供参考）：\n{history_text}\n" if history_text else "")
    long_block = (
        f"长期会话摘要（供参考）：\n{long_term_summary.strip()}\n\n"
        if long_term_summary and long_term_summary.strip() else ""
    )
    user_prompt = (
        long_block + f"用户问题：{question}\n" + history_block + "请直接用中文回答。"
    )
    try:
        if answer_streaming_enabled():
            parts: List[str] = []
            for piece in call_llm_stream(_NON_LEGAL_SYSTEM_PROMPT, user_prompt):
                parts.append(piece)
                emit_answer_token(piece)
            return "".join(parts)
        return call_llm(_NON_LEGAL_SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        return str(e)


# ──────────────────────── 会话长期摘要 ────────────────────────

def summarize_for_memory(chat_history: List[Tuple[str, str]], max_turns: int = 8) -> str:
    pairs = chat_history[-max_turns:] if chat_history else []
    if not pairs:
        return ""
    system_prompt = (
        "你是法律与对话记忆助手。"
        "请将以下对话总结为\"长期会话摘要\"，用于后续问答时提供上下文。"
        "要求：中文；覆盖用户关心的核心法律问题/关键事实/已经得出的要点；"
        "不超过 300 字；尽量用条理化表述。"
    )
    lines: List[str] = []
    for u, a in pairs:
        lines.append(f"用户：{u}")
        lines.append(f"助手：{(a or '')[:200].strip()}")
    user_prompt = "对话内容如下：\n" + "\n".join(lines)
    return call_llm(system_prompt, user_prompt).strip()
