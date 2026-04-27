"""
统一的 LLM 调用封装（OpenAI 兼容接口，默认 DashScope）。
"""
from __future__ import annotations

from typing import Iterator, List

import config


_FALLBACK_MODELS: tuple = (
    "deepseek-v3",
    "deepseek-v3-2",
    "deepseek-v3.2",
    "deepseek-reasoner",
    "deepseek-r1",
    "deepseek-chat",
)


def _candidate_models() -> List[str]:
    seen: set = set()
    out: List[str] = []
    if getattr(config, "LLM_MODEL", None):
        out.append(config.LLM_MODEL)
    out.extend(_FALLBACK_MODELS)
    return [m for m in out if not (m in seen or seen.add(m))]


def _sanitize_error(msg: str) -> str:
    try:
        msg.encode("ascii")
        return msg
    except UnicodeEncodeError:
        return msg.encode("ascii", "backslashreplace").decode("ascii")


def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    """
    调用 OpenAI 兼容 LLM。LLM_API_KEY 未配置时抛 RuntimeError。
    若首选模型返回 404 / 不存在，自动尝试 fallback 模型列表。
    """
    if not config.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY 未配置（OpenAI 兼容接口密钥）。")

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    last_error_msg = ""
    candidates = _candidate_models()
    for model in candidates:
        llm = ChatOpenAI(
            model=model,
            base_url=config.LLM_BASE_URL,
            api_key=config.LLM_API_KEY,
            temperature=temperature,
        )
        try:
            resp = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
            return getattr(resp, "content", str(resp))
        except Exception as e:
            msg = _sanitize_error(str(e))
            last_error_msg = msg
            lowered = msg.lower()
            if ("404" in lowered) or ("does not exist" in lowered) or ("invalid_request_error" in lowered):
                continue
            raise RuntimeError(f"LLM call failed: {msg}") from e

    raise RuntimeError(
        f"LLM call failed for all candidate models. Last error: {last_error_msg}. Candidates: {candidates}"
    )


def _chunk_content(chunk) -> str:
    c = getattr(chunk, "content", None)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: List[str] = []
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif hasattr(block, "text"):
                parts.append(str(getattr(block, "text", "") or ""))
        return "".join(parts)
    return str(c or "")


def call_llm_stream(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> Iterator[str]:
    """
    流式调用 OpenAI 兼容接口；按 token/片段产出增量文本（用于 SSE）。
    与 call_llm 相同的模型回退逻辑。
    """
    if not config.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY 未配置（OpenAI 兼容接口密钥）。")

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    last_error_msg = ""
    candidates = _candidate_models()
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    for model in candidates:
        llm = ChatOpenAI(
            model=model,
            base_url=config.LLM_BASE_URL,
            api_key=config.LLM_API_KEY,
            temperature=temperature,
        )
        try:
            for chunk in llm.stream(messages):
                piece = _chunk_content(chunk)
                if piece:
                    yield piece
            return
        except Exception as e:
            msg = _sanitize_error(str(e))
            last_error_msg = msg
            lowered = msg.lower()
            if ("404" in lowered) or ("does not exist" in lowered) or ("invalid_request_error" in lowered):
                continue
            raise RuntimeError(f"LLM stream failed: {msg}") from e

    raise RuntimeError(
        f"LLM stream failed for all candidate models. Last error: {last_error_msg}. Candidates: {candidates}"
    )
