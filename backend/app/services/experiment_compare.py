"""
实验对照：并行跑各预设 + 可选大模型批量评分。
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import config
from llm_client import call_llm


def _run_single_preset(preset_id: str, question: str, legal_domain: str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    from experiment_design import get_experiment_by_id

    from app.services import rag_bridge

    exp = get_experiment_by_id(preset_id)
    overrides = dict(exp.get("overrides") or {})
    out = rag_bridge.answer(
        question,
        legal_domain=legal_domain or "",
        chat_history=[],
        long_term_summary="",
        runtime_overrides=overrides,
    )
    return preset_id, exp, out


def compare_arms_parallel(preset_ids: List[str], question: str, legal_domain: str) -> List[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    """按 preset_ids 顺序返回 [(pid, exp, rag_out), ...]。"""
    if not preset_ids:
        return []
    max_w = min(4, len(preset_ids))
    with ThreadPoolExecutor(max_workers=max_w) as pool:
        futures = {pool.submit(_run_single_preset, pid, question, legal_domain): pid for pid in preset_ids}
        by_id: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {}
        for fut in as_completed(futures):
            pid, exp, out = fut.result()
            by_id[pid] = (exp, out)
    return [(pid, by_id[pid][0], by_id[pid][1]) for pid in preset_ids]


def _clamp_score(v: Any) -> Optional[int]:
    try:
        x = int(float(v))
        return max(0, min(5, x))
    except (TypeError, ValueError):
        return None


def llm_score_compare_arms(
    question: str,
    arms: List[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    """
    一次 LLM 调用为各臂打分。arms 每项含 preset_id, label, answer, citation_count, intent, skipped_retrieval。
    返回 (preset_id -> {accuracy, evidence, explainability, stability, note}, 跳过或错误说明)。
    """
    if not arms:
        return {}, None
    if not config.LLM_API_KEY:
        return {}, "LLM_API_KEY 未配置，已跳过大模型评分"

    blocks: List[str] = []
    for a in arms:
        pid = str(a.get("preset_id") or "")
        snippet = {
            "preset_id": pid,
            "label": (a.get("label") or "")[:120],
            "intent": a.get("intent") or "",
            "citation_count": int(a.get("citation_count") or 0),
            "skipped_retrieval": bool(a.get("skipped_retrieval")),
            "answer": (a.get("answer") or "")[:4500],
        }
        blocks.append(json.dumps(snippet, ensure_ascii=False))

    system_prompt = (
        "你是法律问答系统的对照实验评测员。给定「同一用户问题」下多个系统配置产出的回答，"
        "请为每一条回答分别打四个整数分（0–5），并给一句简评。\n"
        "维度定义：\n"
        "1) accuracy（准确性）：结论与法律常识/问题要点是否一致，是否存在明显错误。\n"
        "2) evidence（证据充分性）：是否体现检索证据支撑；无引用但说理充分可给中上分；明显臆造法条给低分。\n"
        "3) explainability（可解释性）：是否区分知识库证据与通用说明（如标注「证据[i]」「通用知识」等）。\n"
        "4) stability（稳定性）：本条回答是否自洽、完整、可用；与「其他臂」是否一致不作为扣分点。\n"
        "严格只输出一个 JSON 对象，不要 Markdown 代码块，不要其他文字。格式：\n"
        '{"arms":[{"preset_id":"字符串","accuracy":0,"evidence":0,"explainability":0,"stability":0,"note":"一句话"}]}\n'
        "arms 必须覆盖输入中的全部 preset_id，不得遗漏。"
    )
    user_prompt = (
        f"用户问题：\n{question.strip()[:2000]}\n\n"
        "各配置回答（每行一个 JSON 对象）：\n" + "\n".join(blocks)
    )

    try:
        raw = call_llm(system_prompt, user_prompt)
    except Exception as e:
        return {}, f"大模型评分调用失败：{e}"

    from rag_llm import _safe_json

    try:
        parsed = _safe_json(raw)
    except Exception:
        return {}, "大模型评分返回非合法 JSON，已跳过"

    rows = parsed.get("arms")
    if not isinstance(rows, list):
        return {}, "大模型评分 JSON 缺少 arms 数组"

    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("preset_id") or "").strip()
        if not pid:
            continue
        out[pid] = {
            "accuracy": _clamp_score(row.get("accuracy")),
            "evidence": _clamp_score(row.get("evidence")),
            "explainability": _clamp_score(row.get("explainability")),
            "stability": _clamp_score(row.get("stability")),
            "note": str(row.get("note") or "")[:500],
        }

    missing = [str(a.get("preset_id")) for a in arms if str(a.get("preset_id") or "") not in out]
    if missing:
        return out, f"大模型评分未返回以下 preset_id：{', '.join(missing)}"

    return out, None
