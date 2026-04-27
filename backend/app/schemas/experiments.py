from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    question: str
    legal_domain: str = ""
    preset_ids: list[str] = Field(default_factory=list, max_length=6)
    """是否调用大模型对本次各臂回答做四维打分（同一请求内一次批量评测）。"""
    llm_score: bool = True


class CompareArm(BaseModel):
    preset_id: str
    label: str
    group: str
    latency_ms: int
    citation_count: int
    answer_length: int
    intent: str = ""
    skipped_retrieval: bool = False
    answer: str = ""
    chain_trace_len: int = 0
    llm_accuracy: Optional[int] = Field(default=None, ge=0, le=5)
    llm_evidence: Optional[int] = Field(default=None, ge=0, le=5)
    llm_explainability: Optional[int] = Field(default=None, ge=0, le=5)
    llm_stability: Optional[int] = Field(default=None, ge=0, le=5)
    llm_note: Optional[str] = None


class CompareArmAnalysis(BaseModel):
    """单次对照内横向归一化后的分析行（便于历史回放与表格展示）。"""

    preset_id: str
    label: str
    group: str = ""
    llm_avg: Optional[float] = None
    latency_ms: int = 0
    latency_score_0_1: float = 0.0
    citation_count: int = 0
    citation_score_0_1: float = 0.0
    chain_trace_len: int = 0
    trace_score_0_1: float = 0.0
    composite_0_1: float = 0.0
    rank_composite: int = 0


class CompareAnalysis(BaseModel):
    arms_analysis: list[CompareArmAnalysis]
    recommendation: str
    best_for_quality_preset_id: Optional[str] = None
    best_for_speed_preset_id: Optional[str] = None
    best_balanced_preset_id: Optional[str] = None


class CompareResponse(BaseModel):
    question: str
    legal_domain: str
    arms: list[CompareArm]
    llm_score_note: Optional[str] = None
    run_id: Optional[int] = None
    analysis: Optional[CompareAnalysis] = None


class ExperimentHistoryItem(BaseModel):
    id: int
    question_preview: str
    legal_domain: str
    preset_ids: list[str]
    arm_count: int
    llm_score_enabled: bool
    created_at: str
    best_balanced_label: Optional[str] = None
