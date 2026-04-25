"""检索策略默认值：由知识库构建页写入 runtime_rag_prefs.json。"""

from __future__ import annotations

import json
from typing import Any, Dict

import config

DEFAULT_RAG_PREFS: Dict[str, Any] = {
    "source_mode": "balanced",
    "use_mmr": False,
    "use_rrf": True,
    "use_evidence_labels": True,
    "use_agent_default": False,
    "force_direct_llm": False,
    "enable_agent_fallback": True,
    "active_experiment_preset": "system_full",
}


def _path():
    return getattr(config, "RUNTIME_RAG_PREFS_PATH", config.PROJECT_ROOT / "runtime_rag_prefs.json")


def load_rag_prefs() -> Dict[str, Any]:
    path = _path()
    out = dict(DEFAULT_RAG_PREFS)
    if not path.exists():
        out["use_mmr"] = bool(config.RETRIEVAL_USE_MMR_DEFAULT)
        return out
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k, v in data.items():
                if k in (
                    "source_mode",
                    "use_mmr",
                    "use_rrf",
                    "use_evidence_labels",
                    "use_agent_default",
                    "force_direct_llm",
                    "enable_agent_fallback",
                    "active_experiment_preset",
                ):
                    out[k] = v
    except Exception:
        pass
    if out.get("use_mmr") is None:
        out["use_mmr"] = bool(config.RETRIEVAL_USE_MMR_DEFAULT)
    if out.get("use_rrf") is None:
        out["use_rrf"] = True
    if out.get("use_evidence_labels") is None:
        out["use_evidence_labels"] = True
    if out.get("enable_agent_fallback") is None:
        out["enable_agent_fallback"] = True
    return out


def save_rag_prefs(prefs: Dict[str, Any]) -> None:
    path = _path()
    merged = load_rag_prefs()
    for k in (
        "source_mode",
        "use_mmr",
        "use_rrf",
        "use_evidence_labels",
        "use_agent_default",
        "force_direct_llm",
        "enable_agent_fallback",
        "active_experiment_preset",
    ):
        if k in prefs:
            merged[k] = prefs[k]
    if merged.get("source_mode") not in ("auto", "balanced", "jec_only", "cail_only"):
        merged["source_mode"] = "balanced"
    merged["use_mmr"] = bool(merged.get("use_mmr", False))
    merged["use_rrf"] = bool(merged.get("use_rrf", True))
    merged["use_evidence_labels"] = bool(merged.get("use_evidence_labels", True))
    merged["use_agent_default"] = bool(merged.get("use_agent_default", False))
    merged["force_direct_llm"] = bool(merged.get("force_direct_llm", False))
    merged["enable_agent_fallback"] = bool(merged.get("enable_agent_fallback", True))
    merged["active_experiment_preset"] = str(merged.get("active_experiment_preset", "system_full"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
