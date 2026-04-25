"""
实验日志与会话复盘导出。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import config
from rag_display import unpack_assistant_content


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def append_experiment_turn(record: Dict[str, Any]) -> str:
    _ensure_dir(config.EXPERIMENT_LOG_DIR)
    out_file = config.EXPERIMENT_TURNS_JSONL
    with out_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(out_file)


def build_turn_record(
    session_uuid: str,
    question: str,
    legal_domain: str,
    result: Dict[str, Any],
    experiment: Dict[str, Any],
) -> Dict[str, Any]:
    rs = result.get("retrieval_summary") or {}
    return {
        "ts": _now_iso(),
        "session_uuid": session_uuid,
        "question": question,
        "legal_domain": legal_domain,
        "experiment_id": experiment.get("id", "custom"),
        "experiment_group": experiment.get("group", "custom"),
        "experiment_name": experiment.get("name", "自定义"),
        "experiment_overrides": experiment.get("overrides", {}),
        "runtime_summary": rs,
        "answer": result.get("answer", ""),
        "citations": result.get("citations") or [],
        "chain_trace": result.get("chain_trace") or [],
    }


def export_session_replay(session_uuid: str, messages: List[Dict[str, Any]]) -> str:
    _ensure_dir(config.EXPERIMENT_EXPORT_DIR)
    out_file = config.EXPERIMENT_EXPORT_DIR / f"session_replay_{session_uuid[:8]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jsonl"
    with out_file.open("w", encoding="utf-8") as f:
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "assistant":
                visible_text, bundle = unpack_assistant_content(content)
                payload: Dict[str, Any] = {"role": role, "text": visible_text}
                if bundle:
                    payload["rag_bundle"] = bundle
            else:
                payload = {"role": role, "text": content}
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return str(out_file)
