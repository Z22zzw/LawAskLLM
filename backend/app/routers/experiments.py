from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.experiment import ExperimentCompareRun
from app.models.user import User
from app.schemas.experiments import (
    CompareArm,
    CompareRequest,
    CompareResponse,
    ExperimentHistoryItem,
)
from app.services.experiment_analytics import compute_compare_analysis
from app.services.experiment_compare import compare_arms_parallel, llm_score_compare_arms

router = APIRouter(prefix="/experiments", tags=["实验对照"])


@router.get("/presets")
def list_presets(_: User = Depends(get_current_user)):
    from experiment_design import EXPERIMENT_MATRIX, list_experiment_options

    return {
        "options": list_experiment_options(),
        "matrix": [
            {
                "id": x["id"],
                "group": x["group"],
                "name": x["name"],
                "description": x.get("description", ""),
            }
            for x in EXPERIMENT_MATRIX
        ],
    }


@router.get("/compare/history", response_model=list[ExperimentHistoryItem])
def list_compare_history(
    limit: int = 40,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    limit = max(1, min(100, limit))
    rows = (
        db.query(ExperimentCompareRun)
        .filter(ExperimentCompareRun.user_id == user.id)
        .order_by(ExperimentCompareRun.created_at.desc())
        .limit(limit)
        .all()
    )
    out: list[ExperimentHistoryItem] = []
    for r in rows:
        q = (r.question or "").strip()
        preview = q if len(q) <= 100 else q[:100] + "…"
        pids = list(r.preset_ids or [])
        snap = r.snapshot or {}
        arms = snap.get("arms") or []
        out.append(
            ExperimentHistoryItem(
                id=r.id,
                question_preview=preview,
                legal_domain=r.legal_domain or "",
                preset_ids=pids,
                arm_count=len(arms),
                llm_score_enabled=bool(r.llm_score_enabled),
                created_at=r.created_at.isoformat() if r.created_at else "",
                best_balanced_label=r.best_balanced_label,
            )
        )
    return out


@router.get("/compare/history/{run_id}", response_model=CompareResponse)
def get_compare_history(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = (
        db.query(ExperimentCompareRun)
        .filter(ExperimentCompareRun.id == run_id, ExperimentCompareRun.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    snap = row.snapshot or {}
    try:
        return CompareResponse.model_validate(snap)
    except Exception:
        raise HTTPException(status_code=500, detail="快照数据损坏")


@router.post("/compare", response_model=CompareResponse)
def compare_presets(
    body: CompareRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (body.question or "").strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    ids = [p.strip() for p in body.preset_ids if p and p.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="请至少选择 2 个实验预设进行对照")
    if len(ids) > 4:
        raise HTTPException(status_code=400, detail="最多同时对照 4 个预设")

    q = body.question.strip()
    ld = body.legal_domain or ""

    ordered = compare_arms_parallel(ids, q, ld)

    arms: list[CompareArm] = []
    judge_payload: list[dict] = []
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

    llm_note: str | None = None
    if body.llm_score:
        scores, err = llm_score_compare_arms(q, judge_payload)
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
    best_lbl: str | None = None
    for a in arms:
        if a.preset_id == analysis.best_balanced_preset_id:
            best_lbl = (a.label or "")[:255] or None
            break

    resp = CompareResponse(
        question=q,
        legal_domain=ld,
        arms=arms,
        llm_score_note=llm_note,
        run_id=None,
        analysis=analysis,
    )

    row = ExperimentCompareRun(
        user_id=user.id,
        question=q,
        legal_domain=ld,
        preset_ids=ids,
        llm_score_enabled=bool(body.llm_score),
        best_balanced_label=best_lbl,
        snapshot={},
    )
    db.add(row)
    db.flush()
    resp = resp.model_copy(update={"run_id": row.id})
    row.snapshot = resp.model_dump(mode="json")
    db.commit()

    return resp
