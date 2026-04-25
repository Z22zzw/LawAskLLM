"""
实验设计配置：基线对比 / 策略对比 / 消融实验。
用于前端一键切换实验模式，并将配置写入问答日志。
"""

from __future__ import annotations

from typing import Any, Dict, List


EXPERIMENT_MATRIX: List[Dict[str, Any]] = [
    {
        "id": "baseline_llm_direct",
        "group": "baseline",
        "name": "基线1：仅LLM直答",
        "description": "不走知识库检索，仅用大模型直答。",
        "overrides": {
            "force_direct_llm": True,
            "use_agent_default": False,
            "use_mmr": False,
            "use_rrf": False,
            "use_evidence_labels": False,
            "enable_agent_fallback": False,
            "source_mode": "balanced",
        },
    },
    {
        "id": "baseline_rag_basic",
        "group": "baseline",
        "name": "基线2：基础RAG",
        "description": "仅单轮检索+生成，不启用MMR/RRF和证据相关性标注。",
        "overrides": {
            "force_direct_llm": False,
            "use_agent_default": False,
            "use_mmr": False,
            "use_rrf": False,
            "use_evidence_labels": False,
            "enable_agent_fallback": True,
            "source_mode": "balanced",
        },
    },
    {
        "id": "system_full",
        "group": "baseline",
        "name": "对比组：当前系统完整版",
        "description": "开启多源检索增强、证据标注与Agent异常回退。",
        "overrides": {
            "force_direct_llm": False,
            "use_agent_default": True,
            "use_mmr": True,
            "use_rrf": True,
            "use_evidence_labels": True,
            "enable_agent_fallback": True,
            "source_mode": "balanced",
        },
    },
    {
        "id": "strategy_auto",
        "group": "strategy",
        "name": "策略对比：auto",
        "description": "自动推断检索数据源策略。",
        "overrides": {"source_mode": "auto"},
    },
    {
        "id": "strategy_balanced",
        "group": "strategy",
        "name": "策略对比：balanced",
        "description": "双源均衡召回。",
        "overrides": {"source_mode": "balanced"},
    },
    {
        "id": "strategy_jec_only",
        "group": "strategy",
        "name": "策略对比：jec_only",
        "description": "仅检索JEC-QA。",
        "overrides": {"source_mode": "jec_only"},
    },
    {
        "id": "strategy_cail_only",
        "group": "strategy",
        "name": "策略对比：cail_only",
        "description": "仅检索CAIL2018。",
        "overrides": {"source_mode": "cail_only"},
    },
    {
        "id": "ablation_no_mmr",
        "group": "ablation",
        "name": "消融：去掉MMR",
        "description": "关闭MMR去冗余，其余配置保持系统默认。",
        "overrides": {"use_mmr": False},
    },
    {
        "id": "ablation_no_rrf",
        "group": "ablation",
        "name": "消融：去掉RRF重排",
        "description": "关闭RRF融合与关键词二次重排。",
        "overrides": {"use_rrf": False},
    },
    {
        "id": "ablation_no_evidence_label",
        "group": "ablation",
        "name": "消融：去掉证据相关性标注",
        "description": "关闭strong/weak/unrelated自动标注。",
        "overrides": {"use_evidence_labels": False},
    },
    {
        "id": "ablation_no_agent_fallback",
        "group": "ablation",
        "name": "消融：去掉Agent回退",
        "description": "Agent异常时不再回退LCEL链路。",
        "overrides": {"enable_agent_fallback": False, "use_agent_default": True},
    },
]


EVALUATION_DIMENSIONS: List[Dict[str, str]] = [
    {
        "name": "准确性",
        "desc": "结论是否与法律事实/规则一致。",
        "score_rule": "0-2分：错误；3分：部分正确；4-5分：基本/完全正确。",
    },
    {
        "name": "证据充分性",
        "desc": "结论是否有足够证据支撑。",
        "score_rule": "0-2分：无证据或证据错配；3分：有证据但不充分；4-5分：证据充分且对应明确。",
    },
    {
        "name": "可解释性",
        "desc": "是否清楚区分知识库证据与通用知识补充。",
        "score_rule": "0-2分：无法追溯；3分：部分可追溯；4-5分：可追溯且边界清晰。",
    },
    {
        "name": "稳定性",
        "desc": "异常场景下是否能稳定返回可用结果。",
        "score_rule": "0-2分：频繁失败；3分：偶发失败；4-5分：稳定返回。",
    },
]


SAMPLE_SET_SUGGESTION: Dict[str, Any] = {
    "jec_qa_count": 50,
    "cail2018_count": 50,
    "boundary_count": 20,
    "boundary_types": ["非法律问题", "跨领域问题", "信息不足问题", "术语模糊问题"],
}


def get_experiment_by_id(exp_id: str) -> Dict[str, Any]:
    for item in EXPERIMENT_MATRIX:
        if item.get("id") == exp_id:
            return item
    return {"id": "custom", "group": "custom", "name": "自定义", "description": "", "overrides": {}}


def list_experiment_options() -> List[Dict[str, str]]:
    return [{"id": item["id"], "label": f"[{item['group']}] {item['name']}"} for item in EXPERIMENT_MATRIX]
