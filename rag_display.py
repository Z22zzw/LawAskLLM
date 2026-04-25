"""
对话消息中附加 RAG 元数据（证据列表、检索摘要等），便于历史回放与「展示 RAG 痕迹」开关读取。
正文与 JSON 用固定分隔符拼接，无需改库表结构。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

RAG_META_MARKER = "\n\n---RAG_META_START---\n"


def pack_assistant_content(display_answer: str, bundle: Optional[Dict[str, Any]]) -> str:
    if not bundle:
        return display_answer or ""
    payload = json.dumps(bundle, ensure_ascii=False)
    return (display_answer or "").rstrip() + RAG_META_MARKER + payload


def unpack_assistant_content(content: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    if not content or RAG_META_MARKER not in content:
        return content or "", None
    head, _, tail = content.partition(RAG_META_MARKER)
    try:
        return head, json.loads(tail)
    except json.JSONDecodeError:
        return content, None


def strip_assistant_for_llm(content: str) -> str:
    """供对话历史传入 LLM：去掉 RAG 元数据，仅保留对用户可见正文。"""
    text, _ = unpack_assistant_content(content or "")
    return text


_COVERAGE_LABEL = {
    "full": "命中（强相关）",
    "partial": "部分命中",
    "none": "未命中",
    "": "—",
}

_INTENT_LABEL = {
    "legal": "法律问题",
    "non_legal": "非法律问题（已跳过检索）",
    "": "—",
}


def format_retrieval_summary_markdown(summary: Dict[str, Any]) -> str:
    rp = summary.get("runtime_prefs") or {}
    cs = summary.get("citation_stats") or {}
    ir = summary.get("intent_route") or {}
    intent = summary.get("intent") or ir.get("intent") or ""
    lines = [
        f"- **链路**：`{summary.get('mode', '')}`（LCEL 链式 RAG / Agent）",
        f"- **意图判断**：{_INTENT_LABEL.get(intent, intent)}"
        + (f"（路由来源：`{ir.get('routed_by') or '—'}`）" if ir else ""),
    ]
    if ir.get("route_reason"):
        lines.append(f"- **判断理由**：{ir.get('route_reason')}")
    if ir.get("search_queries"):
        q_list = "、".join(f"`{q}`" for q in ir.get("search_queries") or [])
        lines.append(f"- **检索查询（LLM 建议）**：{q_list}")
    if intent == "legal":
        lines.append(f"- **知识库覆盖**：{_COVERAGE_LABEL.get(summary.get('coverage') or '', summary.get('coverage') or '—')}")

    lines.extend([
        f"- **本轮耗时**：{summary.get('elapsed_sec', 0)} s",
        f"- **Top-K**：{summary.get('top_k', '')}",
        f"- **知识库页配置**：`source_mode={rp.get('source_mode')}`，"
        f"**MMR**={'开启' if rp.get('use_mmr') else '关闭'}，"
        f"**RRF**={'开启' if rp.get('use_rrf', True) else '关闭'}，"
        f"**证据标注**={'开启' if rp.get('use_evidence_labels', True) else '关闭'}，"
        f"**默认 Agent**={'开启' if rp.get('use_agent_default') else '关闭'}",
        f"- **实验开关**：仅LLM直答={'开启' if rp.get('force_direct_llm') else '关闭'}，"
        f"Agent回退={'开启' if rp.get('enable_agent_fallback', True) else '关闭'}，"
        f"实验预设=`{rp.get('active_experiment_preset') or 'custom'}`",
        f"- **实际检索策略**：`{summary.get('effective_source_mode') or '—'}`",
        f"- **法律领域过滤**：{summary.get('legal_domain_label') or '—'}",
        f"- **是否执行向量检索**：{'是' if summary.get('vector_retrieval_ran') else '否'}"
        + ("（澄清分支/非法律分支未检索）" if summary.get("skipped_retrieval") else ""),
        f"- **命中证据**：共 **{cs.get('total', summary.get('evidence_count', 0))}** 条"
        f"（JEC-QA: {cs.get('jec_qa', 0)}，CAIL2018: {cs.get('cail2018', 0)}）",
    ])
    ev_labels = summary.get("evidence_labels") or []
    if ev_labels:
        label_str = "、".join(f"[{i+1}]{lab}" for i, lab in enumerate(ev_labels))
        lines.append(f"- **证据相关性标签**：{label_str}")

    note = summary.get("note")
    if note:
        lines.append(f"- **说明**：{note}")
    return "\n".join(lines)
