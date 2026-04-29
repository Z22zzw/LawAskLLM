"""
对话 SSE 流式：通过 ContextVar 将 trace / token 回调传入 RAG 链，避免改动所有函数签名。
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Callable, Optional

_on_trace_step: ContextVar[Optional[Callable[[str], None]]] = ContextVar("on_trace_step", default=None)
_on_answer_token: ContextVar[Optional[Callable[[str], None]]] = ContextVar("on_answer_token", default=None)


def emit_trace_step(msg: str) -> None:
    cb = _on_trace_step.get()
    if cb:
        cb(msg)


def emit_answer_token(tok: str) -> None:
    if not tok:
        return
    cb = _on_answer_token.get()
    if cb:
        cb(tok)


def answer_streaming_enabled() -> bool:
    """是否已注册答案流式消费端（例如 SSE 线程）。"""
    return _on_answer_token.get() is not None


def set_stream_callbacks(
    on_trace: Optional[Callable[[str], None]],
    on_token: Optional[Callable[[str], None]],
) -> tuple:
    """返回 ContextVar reset 令牌元组，供 finally 调用 reset_stream_callbacks。"""
    return _on_trace_step.set(on_trace), _on_answer_token.set(on_token)


def reset_stream_callbacks(tokens: tuple) -> None:
    _on_trace_step.reset(tokens[0])
    _on_answer_token.reset(tokens[1])
