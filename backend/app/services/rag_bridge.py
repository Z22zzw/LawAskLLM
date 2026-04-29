"""
桥接现有 RAG 模块（项目根目录）到 FastAPI 服务层。
sys.path 已在 app/config.py 中添加项目根目录。
"""
from __future__ import annotations
import time
from typing import Any, Callable, Optional

from app.rag import service as _rag
from app.core.config import RETRIEVAL_TOP_K


def answer(
    question: str,
    legal_domain: str = "",
    chat_history: list | None = None,
    long_term_summary: str = "",
    top_k: int = RETRIEVAL_TOP_K,
    runtime_overrides: dict | None = None,
    on_stream_trace: Optional[Callable[[str], None]] = None,
    on_stream_token: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    """调用现有 rag_service.answer_question，返回原始结果字典。

    on_stream_trace / on_stream_token：由 SSE 等场景注入，经 ContextVar 下发到 RAG 链（同一线程内有效）。
    """
    t0 = time.time()
    ro = dict(runtime_overrides or {})
    if on_stream_trace or on_stream_token:
        from app.rag.stream_callbacks import reset_stream_callbacks, set_stream_callbacks

        tokens = set_stream_callbacks(on_stream_trace, on_stream_token)
        try:
            result = _rag.answer_question(
                question,
                chat_history=chat_history or [],
                top_k=top_k,
                long_term_summary=long_term_summary,
                legal_domain=legal_domain,
                runtime_overrides=ro,
            )
        finally:
            reset_stream_callbacks(tokens)
    else:
        result = _rag.answer_question(
            question,
            chat_history=chat_history or [],
            top_k=top_k,
            long_term_summary=long_term_summary,
            legal_domain=legal_domain,
            runtime_overrides=ro,
        )
    result["_elapsed_ms"] = int((time.time() - t0) * 1000)
    return result


def summarize(pairs: list[tuple[str, str]], max_turns: int = 8) -> str:
    """生成会话长期摘要。"""
    return _rag.summarize_for_memory(pairs[-max_turns:], max_turns=max_turns)
