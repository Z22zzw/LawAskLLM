from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_current_user
from app.models.user import User
from app.schemas.dataset_build import DatasetBuildJobCreate, DatasetBuildJobStatus, DatasetBuildRequest

router = APIRouter(prefix="/dataset-build", tags=["训练集向量库"])

_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _append_log(job_id: str, line: str) -> None:
    with _jobs_lock:
        j = _jobs.get(job_id)
        if not j:
            return
        j.setdefault("logs", []).append(line)
        if len(j["logs"]) > 500:
            j["logs"] = j["logs"][-400:]


def _run_build_job(job_id: str, body: DatasetBuildRequest) -> None:
    from app.core import config as root_config
    from app.knowledge.kb_update import update_vector_store_from_cail2018, update_vector_store_from_jec_qa

    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["logs"] = []
        _jobs[job_id]["total_written"] = 0

    rebuild_once = body.rebuild
    total = 0

    try:
        for item in body.datasets:
            if item.type == "jec":
                if not item.splits:
                    raise ValueError("JEC-QA 未选择任何 split 文件")
                jec_max = None if item.max_items is None or item.max_items <= 0 else int(item.max_items)

                def on_jec(done: int, total_count: int, msg: str) -> None:
                    _append_log(job_id, msg)

                n = update_vector_store_from_jec_qa(
                    rebuild=rebuild_once,
                    splits=tuple(item.splits),
                    max_items=jec_max,
                    progress_callback=on_jec,
                )
                rebuild_once = False
                total += int(n or 0)
                _append_log(job_id, f"JEC-QA 完成，本段写入约 {n} 条。")
                with _jobs_lock:
                    _jobs[job_id]["total_written"] = total

            elif item.type == "cail":
                if not item.splits:
                    raise ValueError("CAIL2018 未选择任何 split 文件")
                cail_max = None if item.max_items is None or item.max_items <= 0 else int(item.max_items)

                def on_cail(cum: int, msg: str) -> None:
                    _append_log(job_id, msg)

                n = update_vector_store_from_cail2018(
                    rebuild=rebuild_once,
                    splits=tuple(item.splits),
                    max_items_per_split=cail_max,
                    progress_callback=on_cail,
                )
                rebuild_once = False
                total += int(n or 0)
                _append_log(job_id, f"CAIL2018 完成，本段写入约 {n} 个向量块。")
                with _jobs_lock:
                    _jobs[job_id]["total_written"] = total

        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["total_written"] = total
        _append_log(job_id, f"全部完成，累计写入约 {total}。")
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)
        _append_log(job_id, f"错误：{e}")


@router.get("/options")
def build_options(_: User = Depends(get_current_user)):
    from app.core import config as root_config

    jec_files = {
        "0_train.json": "训练集（题型0）",
        "1_train.json": "训练集（题型1）",
        "0_test.json": "测试集（题型0）",
        "1_test.json": "测试集（题型1）",
    }
    cail_files = {
        "train.txt": "训练集",
        "dev.txt": "验证集",
        "test.txt": "测试集",
    }
    jec_splits: List[dict] = []
    for fn, label in jec_files.items():
        p = root_config.JEC_QA_DIR / fn
        jec_splits.append({"file": fn, "label": label, "exists": p.exists()})
    cail_splits: List[dict] = []
    for fn, label in cail_files.items():
        p = root_config.CAIL_2018_DIR / fn
        cail_splits.append({"file": fn, "label": label, "exists": p.exists()})
    return {
        "jec_qa_dir": str(root_config.JEC_QA_DIR),
        "cail_dir": str(root_config.CAIL_2018_DIR),
        "jec_splits": jec_splits,
        "cail_splits": cail_splits,
    }


@router.post("/run", response_model=DatasetBuildJobCreate)
def start_build(body: DatasetBuildRequest, _: User = Depends(get_current_user)):
    if not body.datasets:
        raise HTTPException(status_code=400, detail="请至少选择一种数据集配置")
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "pending",
            "logs": [],
            "total_written": 0,
            "error": None,
        }
    t = threading.Thread(target=_run_build_job, args=(job_id, body), daemon=True)
    t.start()
    return DatasetBuildJobCreate(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=DatasetBuildJobStatus)
def job_status(job_id: str, _: User = Depends(get_current_user)):
    with _jobs_lock:
        j = _jobs.get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return DatasetBuildJobStatus(
        job_id=job_id,
        status=j.get("status", "pending"),
        logs=list(j.get("logs") or []),
        total_written=int(j.get("total_written") or 0),
        error=j.get("error"),
    )
