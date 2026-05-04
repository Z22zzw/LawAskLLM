"""读取脚本导出的 20 题实验 CSV，并聚合为前端仪表盘数据。"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

from app.core import config
from app.schemas.experiments import (
    BatchAblationDelta,
    BatchDashboardResponse,
    BatchDashboardSummary,
    BatchMetricSummary,
    BatchPresetSummary,
    BatchQuestionResult,
)


EXP_LABELS = {
    "A": "实验一：基线对比",
    "B": "实验二：数据源策略",
    "C1": "实验三-1：去掉 MMR",
    "C2": "实验三-2：去掉 RRF",
    "C3": "实验三-3：去掉证据标注",
    "C4": "实验三-4：去掉 Agent 回退",
}

BLOCK_LABELS = {
    "A_concept": "A 类：法考 / 概念解释",
    "B_case": "B 类：刑事案情 / 罪名量刑",
    "C_boundary": "C 类：边界与鲁棒性",
}


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(v: Any) -> int:
    f = _to_float(v)
    return int(f) if f is not None else 0


def _round(v: Optional[float], digits: int = 4) -> Optional[float]:
    if v is None:
        return None
    return round(v, digits)


def _avg(values: Iterable[Optional[float]]) -> Optional[float]:
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _is_success(row: dict[str, str]) -> bool:
    return str(row.get("status") or "").lower().startswith("success")


def _has_llm(row: dict[str, str]) -> bool:
    if _to_float(row.get("llm_avg")) is not None:
        return True
    for k in ("llm_accuracy", "llm_evidence", "llm_explainability", "llm_stability"):
        if _to_float(row.get(k)) is not None:
            return True
    return False


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _read_meta(path: Path) -> dict[str, Any]:
    meta_path = path.parent / "experiment_batch_meta.json"
    if not meta_path.exists():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _candidate_paths(project_root: Path) -> list[tuple[str, Path]]:
    base = project_root / "实验结果"
    return [
        ("大模型评分", base / "大模型评分" / "exp_all.csv"),
        ("大模型不评分", base / "大模型不评分" / "exp_all.csv"),
        ("根目录", project_root / "exp_all.csv"),
    ]


def _choose_source(project_root: Path) -> tuple[str, Path, list[dict[str, str]], dict[str, Any]]:
    existing: list[tuple[str, Path, list[dict[str, str]], dict[str, Any]]] = []
    for kind, path in _candidate_paths(project_root):
        if not path.exists():
            continue
        rows = _read_csv(path)
        existing.append((kind, path, rows, _read_meta(path)))
        if kind == "大模型评分" and any(_has_llm(r) for r in rows):
            return existing[-1]
    if existing:
        return existing[0]
    raise FileNotFoundError("未找到 exp_all.csv")


def _summary_rows(rows: list[dict[str, str]], key: str, labels: dict[str, str]) -> list[BatchMetricSummary]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "未分组")].append(row)

    out: list[BatchMetricSummary] = []
    for k, items in grouped.items():
        out.append(
            BatchMetricSummary(
                key=k,
                label=labels.get(k, k),
                row_count=len(items),
                success_rate=_round(sum(1 for r in items if _is_success(r)) / len(items), 4) or 0.0,
                avg_composite=_round(_avg(_to_float(r.get("composite_0_1")) for r in items)),
                avg_llm=_round(_avg(_to_float(r.get("llm_avg")) for r in items)),
                avg_latency_ms=_round(_avg(_to_float(r.get("latency_ms")) for r in items), 2),
                avg_citation_count=_round(_avg(_to_float(r.get("citation_count")) for r in items), 2),
            )
        )
    return sorted(out, key=lambda x: x.key)


def _preset_rows(rows: list[dict[str, str]]) -> list[BatchPresetSummary]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("preset_id") or "unknown")].append(row)

    out: list[BatchPresetSummary] = []
    for pid, items in grouped.items():
        first = items[0]
        out.append(
            BatchPresetSummary(
                key=pid,
                preset_id=pid,
                label=str(first.get("label") or pid),
                group=str(first.get("group") or ""),
                is_control=pid == "system_full" or str(first.get("is_control") or "") == "1",
                row_count=len(items),
                success_rate=_round(sum(1 for r in items if _is_success(r)) / len(items), 4) or 0.0,
                avg_composite=_round(_avg(_to_float(r.get("composite_0_1")) for r in items)),
                avg_llm=_round(_avg(_to_float(r.get("llm_avg")) for r in items)),
                avg_latency_ms=_round(_avg(_to_float(r.get("latency_ms")) for r in items), 2),
                avg_citation_count=_round(_avg(_to_float(r.get("citation_count")) for r in items), 2),
            )
        )
    return sorted(out, key=lambda x: (x.avg_composite is None, -(x.avg_composite or 0), x.preset_id))


def _ablation_deltas(rows: list[dict[str, str]]) -> list[BatchAblationDelta]:
    by_exp_question: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        exp = str(row.get("exp") or "")
        if exp.startswith("C"):
            by_exp_question[(exp, str(row.get("question_id") or ""))].append(row)

    acc: dict[str, dict[str, list[float] | str]] = {}
    for (exp, _qid), items in by_exp_question.items():
        control = next((r for r in items if r.get("preset_id") == "system_full"), None)
        ablation = next((r for r in items if r.get("preset_id") != "system_full"), None)
        if not control or not ablation:
            continue
        bucket = acc.setdefault(
            exp,
            {
                "preset_id": str(ablation.get("preset_id") or ""),
                "composite": [],
                "llm": [],
                "citation": [],
                "latency": [],
            },
        )
        for metric, field in (
            ("composite", "composite_0_1"),
            ("llm", "llm_avg"),
            ("citation", "citation_count"),
            ("latency", "latency_ms"),
        ):
            a = _to_float(control.get(field))
            b = _to_float(ablation.get(field))
            if a is not None and b is not None:
                bucket[metric].append(a - b)  # type: ignore[index, union-attr]

    out: list[BatchAblationDelta] = []
    for exp, data in acc.items():
        preset_id = str(data.get("preset_id") or "")
        out.append(
            BatchAblationDelta(
                exp=exp,
                label=EXP_LABELS.get(exp, exp),
                ablation_preset_id=preset_id,
                question_count=len(data["composite"]),  # type: ignore[arg-type, index]
                composite_delta=_round(_avg(data["composite"])),  # type: ignore[arg-type, index]
                llm_delta=_round(_avg(data["llm"])),  # type: ignore[arg-type, index]
                citation_delta=_round(_avg(data["citation"]), 2),  # type: ignore[arg-type, index]
                latency_delta_ms=_round(_avg(data["latency"]), 2),  # type: ignore[arg-type, index]
            )
        )
    return sorted(out, key=lambda x: x.exp)


def _question_results(rows: list[dict[str, str]]) -> list[BatchQuestionResult]:
    out: list[BatchQuestionResult] = []
    for row in rows:
        out.append(
            BatchQuestionResult(
                exp=str(row.get("exp") or ""),
                question_id=_to_int(row.get("question_id")),
                block=str(row.get("block") or ""),
                question_preview=str(row.get("question_preview") or ""),
                preset_id=str(row.get("preset_id") or ""),
                label=str(row.get("label") or row.get("preset_id") or ""),
                group=str(row.get("group") or ""),
                is_control=str(row.get("is_control") or "") == "1" or row.get("preset_id") == "system_full",
                status=str(row.get("status") or ""),
                latency_ms=_to_float(row.get("latency_ms")),
                citation_count=_to_float(row.get("citation_count")),
                llm_avg=_to_float(row.get("llm_avg")),
                composite_0_1=_to_float(row.get("composite_0_1")),
                llm_score_note=str(row.get("llm_score_note") or ""),
            )
        )
    return sorted(out, key=lambda x: (x.question_id, x.exp, 0 if x.is_control else 1, x.preset_id))


def _build_ai_summary(resp: BatchDashboardResponse) -> str:
    if not resp.available:
        return ""
    best = resp.preset_summaries[0] if resp.preset_summaries else None
    best_text = f"`{best.preset_id}`（{best.label}）" if best else "暂无"
    score_note = "包含大模型四维评分" if resp.summary.has_llm_scores else "当前结果未获得有效大模型四维评分，主要依据客观指标与综合分"
    lines = [
        "### 总体结论",
        f"本次批跑覆盖 {resp.summary.total_questions} 道题、{resp.summary.total_rows} 条实验臂记录，成功率约 {resp.summary.success_rate:.0%}，{score_note}。综合排序当前领先的是 {best_text}。",
        "",
        "### 三组实验解读",
        "- **基线对比**：用于说明完整系统相对仅 LLM 直答与基础 RAG 的整体收益，重点看综合分、引用数与可解释性。",
        "- **数据源策略**：用于比较 balanced 对照下 auto、JEC-only、CAIL-only 的检索适配性，重点看不同题型分组上的差异。",
        "- **消融实验**：用于判断 MMR、RRF、证据标注、Agent 回退的贡献，若差值为正，说明完整系统在该指标上优于去掉模块后的版本。",
        "",
        "### 使用提示",
        "若 `llm_score_note` 显示密钥未配置或评分缺失，应把大模型评分结论降级为参考，并优先依赖人工复核与客观指标。",
    ]
    if resp.ablation_deltas:
        strongest = max(resp.ablation_deltas, key=lambda x: x.composite_delta or 0)
        lines.insert(
            6,
            f"当前消融中，`{strongest.ablation_preset_id}` 相对完整系统的综合分差值最大（{strongest.composite_delta or 0:.3f}），可优先作为模块贡献讨论对象。",
        )
    return "\n".join(lines)


def load_batch_dashboard(project_root: Optional[Path] = None) -> BatchDashboardResponse:
    root = project_root or config.PROJECT_ROOT
    try:
        source_kind, source_path, rows, meta = _choose_source(root)
    except FileNotFoundError:
        return BatchDashboardResponse(
            available=False,
            message="未找到批跑 CSV。请先运行 scripts/run_experiment_batch.py，并将结果输出到 实验结果/大模型评分 或 实验结果/大模型不评分。",
        )

    success_rows = sum(1 for row in rows if _is_success(row))
    total_rows = len(rows)
    summary = BatchDashboardSummary(
        total_questions=len({str(r.get("question_id") or "") for r in rows if r.get("question_id")}),
        total_rows=total_rows,
        success_rows=success_rows,
        success_rate=_round(success_rows / total_rows, 4) if total_rows else 0.0,
        exp_count=len({str(r.get("exp") or "") for r in rows if r.get("exp")}),
        has_llm_scores=any(_has_llm(r) for r in rows),
        avg_composite=_round(_avg(_to_float(r.get("composite_0_1")) for r in rows)),
        avg_llm=_round(_avg(_to_float(r.get("llm_avg")) for r in rows)),
    )

    resp = BatchDashboardResponse(
        available=True,
        message="已读取最近一次脚本实验结果。",
        source_kind=source_kind,
        source_path=str(source_path),
        meta=meta,
        summary=summary,
        exp_summaries=_summary_rows(rows, "exp", EXP_LABELS),
        block_summaries=_summary_rows(rows, "block", BLOCK_LABELS),
        preset_summaries=_preset_rows(rows),
        ablation_deltas=_ablation_deltas(rows),
        question_results=_question_results(rows),
    )
    resp.ai_summary = _build_ai_summary(resp)
    if source_kind == "大模型评分" and not summary.has_llm_scores:
        resp.message = "已读取大模型评分目录，但 CSV 中没有有效四维评分；请检查 LLM_API_KEY 或查看 llm_score_note。"
    return resp
