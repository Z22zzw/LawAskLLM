"""
实验对照结果：归一化指标、综合排序与「如何选择」说明文案。
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from app.schemas.experiments import CompareAnalysis, CompareArm, CompareArmAnalysis


def _llm_avg(a: CompareArm) -> Optional[float]:
    dims = [a.llm_accuracy, a.llm_evidence, a.llm_explainability, a.llm_stability]
    nums = [x for x in dims if isinstance(x, int)]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _norm_range(vals: List[float], v: float) -> float:
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return 1.0
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


def compute_compare_analysis(arms: List[CompareArm]) -> CompareAnalysis:
    """在同一次对照内做横向归一化与综合分，生成选型建议。"""
    n = len(arms)
    if n == 0:
        return CompareAnalysis(
            arms_analysis=[],
            recommendation="暂无数据。",
            best_for_quality_preset_id=None,
            best_for_speed_preset_id=None,
            best_balanced_preset_id=None,
        )

    latencies = [float(a.latency_ms) for a in arms]
    cites = [float(a.citation_count) for a in arms]
    traces = [float(a.chain_trace_len) for a in arms]
    llm_avgs = [_llm_avg(a) for a in arms]

    rows: List[CompareArmAnalysis] = []
    for idx, a in enumerate(arms):
        lat_s = 1.0 - _norm_range(latencies, float(a.latency_ms))
        cit_s = _norm_range(cites, float(a.citation_count))
        tr_s = _norm_range(traces, float(a.chain_trace_len))
        la = llm_avgs[idx]
        if la is not None:
            composite = 0.58 * (la / 5.0) + 0.22 * lat_s + 0.12 * cit_s + 0.08 * tr_s
        else:
            composite = 0.45 * lat_s + 0.35 * cit_s + 0.20 * tr_s
        rows.append(
            CompareArmAnalysis(
                preset_id=a.preset_id,
                label=a.label,
                group=a.group,
                llm_avg=round(la, 2) if la is not None else None,
                latency_ms=a.latency_ms,
                latency_score_0_1=round(lat_s, 3),
                citation_count=a.citation_count,
                citation_score_0_1=round(cit_s, 3),
                chain_trace_len=a.chain_trace_len,
                trace_score_0_1=round(tr_s, 3),
                composite_0_1=round(composite, 3),
                rank_composite=0,
            )
        )

    order = sorted(range(n), key=lambda i: rows[i].composite_0_1, reverse=True)
    rank_map = {order[r]: r + 1 for r in range(n)}
    rows = [rows[i].model_copy(update={"rank_composite": rank_map[i]}) for i in range(n)]

    valid_llm = [(i, llm_avgs[i]) for i in range(n) if llm_avgs[i] is not None]
    if valid_llm:
        best_q_idx = max(valid_llm, key=lambda t: t[1])[0]
        best_q = arms[best_q_idx].preset_id
        q_label = arms[best_q_idx].label
    else:
        best_q = None
        q_label = None

    best_s_idx = min(range(n), key=lambda i: arms[i].latency_ms)
    best_s = arms[best_s_idx].preset_id
    s_label = arms[best_s_idx].label

    best_b_idx = order[0]
    best_b = arms[best_b_idx].preset_id
    b_label = arms[best_b_idx].label

    if q_label:
        rec_q = (
            f"**质量优先（正确性、证据与可解释性）**：本次大模型四维均分最高的是「{q_label}」。"
            "若问题涉及严肃法律结论或需要向他人展示依据，应优先参考该臂，并结合引用条数与链式步骤核对检索是否到位。"
        )
    else:
        rec_q = (
            "**质量优先**：本次未启用或未返回大模型评分，不宜仅凭字数或延迟判断优劣；建议重新运行并开启「大模型四维评分」，或人工对照各臂回答与引用。"
        )

    rec_s = (
        f"**速度优先（交互与批量评测）**：延迟最低的是「{s_label}」。"
        "在演示、压测或弱网下可优先选用；若延迟明显低于其他臂但引用很少，需警惕是否走了「仅 LLM / 跳过检索」路径。"
    )

    rec_b = (
        f"**综合平衡（本页默认加权）**：按「质量 58% + 相对速度 22% + 相对引用 12% + 链深度 8%」估算，综合分最高的是「{b_label}」。"
        "该权重偏向「答得好」而非「极致快」；若你的场景更重视合规可追溯，可适当提高大模型各维或引用条数在心中的权重。"
    )

    rec_how = (
        "**如何选更优秀**：(1) 同一问题上多臂分数接近时，看「证据充分性」与「可解释性」是否满足你的交付要求；"
        "(2) 引用条数为 0 且意图为法律问题时，确认是否为直答或 Agent 未落结构化引用；"
        "(3) 消融实验看的是「相对系统完整版」的得失，应结合下表归一化列判断哪项能力被关掉后下降最明显。"
    )

    return CompareAnalysis(
        arms_analysis=rows,
        recommendation="\n\n".join([rec_q, rec_s, rec_b, rec_how]),
        best_for_quality_preset_id=best_q,
        best_for_speed_preset_id=best_s,
        best_balanced_preset_id=best_b,
    )
