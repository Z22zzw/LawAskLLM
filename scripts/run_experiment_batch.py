#!/usr/bin/env python3
"""
批量运行实验 A/B/C，输出 CSV 至项目根目录。

实验设计（与 backend/app/experiments/design.py 一致）：
  A：system_full, baseline_llm_direct, baseline_rag_basic
  B：system_full, strategy_auto, strategy_jec_only, strategy_cail_only
  C：四轮，每轮 system_full + 一条消融臂

运行前会将 runtime_rag_prefs.json 备份并写入与 system_full 一致的检索开关，
结束后恢复原文件（策略/消融预设仅覆盖部分键，依赖 prefs 与完整版对齐）。

用法（在仓库根目录）：
  cd backend && PYTHONPATH=. python ../scripts/run_experiment_batch.py
  cd backend && PYTHONPATH=. python ../scripts/run_experiment_batch.py --max-questions 2 --only A
  cd backend && PYTHONPATH=. python ../scripts/run_experiment_batch.py --no-llm-score
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 仓库根与 backend 路径
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND))

# 先于 app.config 导入加载 .env，使 LLM_API_KEY 可用于大模型评委
try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass


def _reload_config_llm_key() -> None:
    """dotenv 加载后刷新 config 中的 LLM_API_KEY（config 在首次 import 时已读环境变量）。"""
    import os

    from app.core import config as _cfg
    from app.core.config import _is_placeholder_key

    k = (os.getenv("LLM_API_KEY") or "").strip()
    if _is_placeholder_key(k):
        k = ""
    _cfg.LLM_API_KEY = k

SYSTEM_FULL_PREFS: Dict[str, Any] = {
    "source_mode": "balanced",
    "use_mmr": True,
    "use_rrf": True,
    "use_evidence_labels": True,
    "use_agent_default": True,
    "force_direct_llm": False,
    "enable_agent_fallback": True,
    "active_experiment_preset": "system_full",
}

EXP_A = ["system_full", "baseline_llm_direct", "baseline_rag_basic"]
EXP_B = ["system_full", "strategy_auto", "strategy_jec_only", "strategy_cail_only"]
EXP_C_ROUNDS = [
    ("C1", ["system_full", "ablation_no_mmr"]),
    ("C2", ["system_full", "ablation_no_rrf"]),
    ("C3", ["system_full", "ablation_no_evidence_label"]),
    ("C4", ["system_full", "ablation_no_agent_fallback"]),
]


def _parse_questions(md_path: Path) -> List[Tuple[int, str, str]]:
    """返回 [(question_id, block, text), ...]"""
    text = md_path.read_text(encoding="utf-8")
    rows: List[Tuple[int, str, str]] = []
    for line in text.splitlines():
        m = re.match(r"^(\d+)\.\s+(.+)$", line.strip())
        if not m:
            continue
        qid = int(m.group(1))
        qtext = m.group(2).strip()
        if qid <= 8:
            block = "A_concept"
        elif qid <= 16:
            block = "B_case"
        else:
            block = "C_boundary"
        rows.append((qid, block, qtext))
    rows.sort(key=lambda x: x[0])
    return rows


def _freeze_and_apply_system_full_prefs() -> Tuple[Any, Optional[str], bool]:
    """备份当前 prefs；返回 (prefs_path, backup_text, 原文件是否存在)。"""
    from app.core import config
    from app.rag.prefs import save_rag_prefs

    path = getattr(config, "RUNTIME_RAG_PREFS_PATH", config.PROJECT_ROOT / "runtime_rag_prefs.json")
    backup: Optional[str] = None
    existed = path.exists()
    if existed:
        backup = path.read_text(encoding="utf-8")
    save_rag_prefs(SYSTEM_FULL_PREFS)
    return path, backup, existed


def _restore_prefs(path: Path, backup: Optional[str], had_existed: bool) -> None:
    if had_existed and backup is not None:
        path.write_text(backup, encoding="utf-8")
    elif not had_existed and path.exists():
        path.unlink()


def _run_compare_like_api(
    preset_ids: List[str],
    question: str,
    legal_domain: str,
    llm_score: bool,
) -> Tuple[List[Any], Optional[Any], Optional[str]]:
    from app.experiments.analytics import compute_compare_analysis
    from app.experiments.compare import compare_arms_parallel, llm_score_compare_arms
    from app.schemas.experiments import CompareArm

    ordered = compare_arms_parallel(preset_ids, question.strip(), legal_domain or "")
    arms: List[CompareArm] = []
    judge_payload: List[dict] = []
    for _pid, exp, out in ordered:
        pid = str(exp.get("id", _pid))
        ans = out.get("answer") or ""
        cites = out.get("citations") or []
        trace = out.get("chain_trace") or []
        intent = str(out.get("intent") or "")
        arms.append(
            CompareArm(
                preset_id=pid,
                label=str(exp.get("name", pid)),
                group=str(exp.get("group", "")),
                latency_ms=int(out.get("_elapsed_ms") or 0),
                citation_count=len(cites),
                answer_length=len(ans),
                intent=intent,
                skipped_retrieval=bool(out.get("skipped_retrieval")),
                answer=ans,
                chain_trace_len=len(trace),
            )
        )
        judge_payload.append(
            {
                "preset_id": pid,
                "label": str(exp.get("name", pid)),
                "answer": ans,
                "citation_count": len(cites),
                "intent": intent,
                "skipped_retrieval": bool(out.get("skipped_retrieval")),
            }
        )

    llm_note: Optional[str] = None
    if llm_score:
        scores, err = llm_score_compare_arms(question.strip(), judge_payload)
        if err:
            llm_note = err
        for arm in arms:
            s = scores.get(arm.preset_id)
            if not s:
                continue
            arm.llm_accuracy = s.get("accuracy")
            arm.llm_evidence = s.get("evidence")
            arm.llm_explainability = s.get("explainability")
            arm.llm_stability = s.get("stability")
            arm.llm_note = s.get("note") or None
    else:
        llm_note = "已关闭大模型评分"

    analysis = compute_compare_analysis(arms)
    return arms, analysis, llm_note


def _arm_analysis_map(analysis: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not analysis or not getattr(analysis, "arms_analysis", None):
        return out
    for row in analysis.arms_analysis:
        out[row.preset_id] = row
    return out


def _llm_avg(arm: Any) -> Optional[float]:
    dims = [arm.llm_accuracy, arm.llm_evidence, arm.llm_explainability, arm.llm_stability]
    nums = [x for x in dims if isinstance(x, int)]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 4)


CSV_COLUMNS = [
    "exp",
    "question_id",
    "block",
    "legal_domain",
    "preset_id",
    "label",
    "group",
    "is_control",
    "latency_ms",
    "citation_count",
    "answer_length",
    "chain_trace_len",
    "intent",
    "skipped_retrieval",
    "llm_accuracy",
    "llm_evidence",
    "llm_explainability",
    "llm_stability",
    "llm_avg",
    "llm_note",
    "llm_score_note",
    "latency_score_0_1",
    "citation_score_0_1",
    "trace_score_0_1",
    "composite_0_1",
    "rank_composite",
    "question_preview",
    "status",
    "created_at_utc",
    "prefs_frozen",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="批量实验对照并导出 CSV")
    parser.add_argument(
        "--questions-md",
        type=Path,
        default=_REPO_ROOT / "实验题单_20题_小样本.md",
        help="题单 Markdown 路径",
    )
    parser.add_argument("--legal-domain", default="", help="法律领域，全程固定")
    parser.add_argument("--max-questions", type=int, default=0, help="最多跑前几题，0 表示全部")
    parser.add_argument("--only", choices=("A", "B", "C", "all"), default="all", help="只跑某一类实验")
    parser.add_argument("--no-llm-score", action="store_true", help="关闭四维 LLM 评分（更快、省 API）")
    parser.add_argument("--out-dir", type=Path, default=_REPO_ROOT, help="CSV 输出目录，默认仓库根目录")
    args = parser.parse_args()

    _reload_config_llm_key()

    questions = _parse_questions(args.questions_md)
    if not questions:
        print("未从题单解析到题目，请检查文件格式（行首为「数字. 」）", file=sys.stderr)
        return 1
    if args.max_questions and args.max_questions > 0:
        questions = [q for q in questions if q[0] <= args.max_questions]

    llm_score = not args.no_llm_score
    created_at = datetime.now(timezone.utc).isoformat()
    prefs_path, backup, prefs_existed_before = _freeze_and_apply_system_full_prefs()
    print(f"已冻结 prefs 至 system_full 等价项，文件：{prefs_path}")

    all_rows: List[Dict[str, Any]] = []

    def append_rows_for_exp(exp_code: str, preset_ids: List[str], qid: int, block: str, qtext: str) -> None:
        nonlocal all_rows
        status = "success"
        arms = None
        analysis = None
        llm_note = None
        try:
            arms, analysis, llm_note = _run_compare_like_api(preset_ids, qtext, args.legal_domain, llm_score)
        except Exception as e:
            status = f"failed:{e}"
            row_base = {
                "exp": exp_code,
                "question_id": qid,
                "block": block,
                "legal_domain": args.legal_domain,
                "question_preview": (qtext[:200] + "…") if len(qtext) > 200 else qtext,
                "status": status,
                "created_at_utc": created_at,
                "prefs_frozen": "system_full",
            }
            for pid in preset_ids:
                all_rows.append(
                    {
                        **row_base,
                        "preset_id": pid,
                        "label": "",
                        "group": "",
                        "is_control": 1 if pid == "system_full" else 0,
                        "latency_ms": "",
                        "citation_count": "",
                        "answer_length": "",
                        "chain_trace_len": "",
                        "intent": "",
                        "skipped_retrieval": "",
                        "llm_accuracy": "",
                        "llm_evidence": "",
                        "llm_explainability": "",
                        "llm_stability": "",
                        "llm_avg": "",
                        "llm_note": "",
                        "llm_score_note": str(e),
                        "latency_score_0_1": "",
                        "citation_score_0_1": "",
                        "trace_score_0_1": "",
                        "composite_0_1": "",
                        "rank_composite": "",
                    }
                )
            return

        amap = _arm_analysis_map(analysis)
        preview = (qtext[:200] + "…") if len(qtext) > 200 else qtext
        for arm in arms or []:
            aa = amap.get(arm.preset_id)
            all_rows.append(
                {
                    "exp": exp_code,
                    "question_id": qid,
                    "block": block,
                    "legal_domain": args.legal_domain,
                    "preset_id": arm.preset_id,
                    "label": arm.label,
                    "group": arm.group,
                    "is_control": 1 if arm.preset_id == "system_full" else 0,
                    "latency_ms": arm.latency_ms,
                    "citation_count": arm.citation_count,
                    "answer_length": arm.answer_length,
                    "chain_trace_len": arm.chain_trace_len,
                    "intent": arm.intent,
                    "skipped_retrieval": arm.skipped_retrieval,
                    "llm_accuracy": arm.llm_accuracy if arm.llm_accuracy is not None else "",
                    "llm_evidence": arm.llm_evidence if arm.llm_evidence is not None else "",
                    "llm_explainability": arm.llm_explainability if arm.llm_explainability is not None else "",
                    "llm_stability": arm.llm_stability if arm.llm_stability is not None else "",
                    "llm_avg": _llm_avg(arm) if _llm_avg(arm) is not None else "",
                    "llm_note": arm.llm_note or "",
                    "llm_score_note": llm_note or "",
                    "latency_score_0_1": aa.latency_score_0_1 if aa else "",
                    "citation_score_0_1": aa.citation_score_0_1 if aa else "",
                    "trace_score_0_1": aa.trace_score_0_1 if aa else "",
                    "composite_0_1": aa.composite_0_1 if aa else "",
                    "rank_composite": aa.rank_composite if aa else "",
                    "question_preview": preview,
                    "status": status,
                    "created_at_utc": created_at,
                    "prefs_frozen": "system_full",
                }
            )

    try:
        run_a = args.only in ("all", "A")
        run_b = args.only in ("all", "B")
        run_c = args.only in ("all", "C")

        for qid, block, qtext in questions:
            if run_a:
                print(f"[A] q={qid} …")
                append_rows_for_exp("A", EXP_A, qid, block, qtext)
            if run_b:
                print(f"[B] q={qid} …")
                append_rows_for_exp("B", EXP_B, qid, block, qtext)
            if run_c:
                for code, pids in EXP_C_ROUNDS:
                    print(f"[{code}] q={qid} …")
                    append_rows_for_exp(code, pids, qid, block, qtext)
    finally:
        _restore_prefs(prefs_path, backup, prefs_existed_before)
        print("已恢复 runtime_rag_prefs.json")

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    def write_csv(name: str, rows: List[Dict[str, Any]]) -> Path:
        path = out_dir / name
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
        return path

    meta = {
        "created_at_utc": created_at,
        "legal_domain": args.legal_domain,
        "llm_score": llm_score,
        "questions_file": str(args.questions_md),
        "max_questions": args.max_questions or "all",
        "only": args.only,
        "prefs_frozen": "system_full",
    }
    (out_dir / "experiment_batch_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    path_all = write_csv("exp_all.csv", all_rows)
    write_csv("exp_A.csv", [r for r in all_rows if r["exp"] == "A"])
    write_csv("exp_B.csv", [r for r in all_rows if r["exp"] == "B"])
    for code, _ in EXP_C_ROUNDS:
        write_csv(f"exp_{code}.csv", [r for r in all_rows if r["exp"] == code])

    print(f"完成：共 {len(all_rows)} 行，汇总 {path_all}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
