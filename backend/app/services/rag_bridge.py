"""
桥接现有 RAG 模块（项目根目录）到 FastAPI 服务层。
sys.path 已在 app/config.py 中添加项目根目录。
"""
from __future__ import annotations
import time
from typing import Any

import rag_service as _rag
from config import RETRIEVAL_TOP_K


def answer(
    question: str,
    legal_domain: str = "",
    chat_history: list | None = None,
    long_term_summary: str = "",
    top_k: int = RETRIEVAL_TOP_K,
    runtime_overrides: dict | None = None,
) -> dict[str, Any]:
    """调用现有 rag_service.answer_question，返回原始结果字典。"""
    t0 = time.time()
    result = _rag.answer_question(
        question,
        chat_history=chat_history or [],
        top_k=top_k,
        long_term_summary=long_term_summary,
        legal_domain=legal_domain,
        runtime_overrides=runtime_overrides or {},
    )
    result["_elapsed_ms"] = int((time.time() - t0) * 1000)
    return result


def summarize(pairs: list[tuple[str, str]], max_turns: int = 8) -> str:
    """生成会话长期摘要。"""
    return _rag.summarize_for_memory(pairs[-max_turns:], max_turns=max_turns)
