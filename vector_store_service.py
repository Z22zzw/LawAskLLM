import shutil
import time
from pathlib import Path
from typing import Optional

import config


def build_tongyi_embeddings():
    """
    LangChain 社区中通常使用 DashScopeEmbeddings 来实现通义千问/通义嵌入（TongyiEmbeddings 的等价实现）。
    """
    if not config.DASHSCOPE_API_KEY:
        raise RuntimeError(
            "未配置 DASHSCOPE_API_KEY。请在环境变量中设置后再运行（用于 Tongyi/DashScope Embeddings）。"
        )

    try:
        # langchain-community 推荐路径
        from langchain_community.embeddings import DashScopeEmbeddings
    except ImportError as e:
        raise RuntimeError("未安装 langchain-community，或 Tongyi/DashScopeEmbeddings 导入失败。") from e

    return DashScopeEmbeddings(
        model="text-embedding-v3",
        dashscope_api_key=config.DASHSCOPE_API_KEY,
    )


def get_chroma_vector_store(persist_dir: Optional[Path] = None):
    persist_dir = persist_dir or config.VECTOR_DB_DIR
    persist_dir.mkdir(parents=True, exist_ok=True)

    embedding = build_tongyi_embeddings()

    try:
        from langchain_community.vectorstores import Chroma
    except ImportError as e:
        raise RuntimeError("未安装 chromadb / langchain-community，或 Chroma 导入失败。") from e

    return Chroma(
        collection_name="law_rag",
        persist_directory=str(persist_dir),
        embedding_function=embedding,
    )


def reset_vector_store(persist_dir: Optional[Path] = None):
    """
    删除持久化目录，下一次会重新从数据构建向量库。
    """
    persist_dir = persist_dir or config.VECTOR_DB_DIR
    if persist_dir.exists():
        # Windows：另一 Streamlit（对话页）或其它进程打开 chroma.sqlite3 时，rmtree 会 WinError 32。
        # 多轮重试给人工关页面 / 进程释放句柄的时间；可用环境变量调大。
        last_err = None
        n = config.VECTOR_DB_RESET_MAX_ATTEMPTS
        delay = config.VECTOR_DB_RESET_RETRY_DELAY_SEC
        for attempt in range(n):
            try:
                shutil.rmtree(persist_dir)
                last_err = None
                break
            except PermissionError as e:
                last_err = e
                if attempt < n - 1:
                    time.sleep(delay)

        if last_err is not None and persist_dir.exists():
            raise PermissionError(
                f"无法重建向量库目录：{persist_dir} 仍被占用（常见为 chroma.sqlite3 被其它进程打开）。\n"
                "请依次尝试：\n"
                "1) 关闭「对话」页的 Streamlit：运行了 `python start.py` 的终端里按 Ctrl+C（默认端口 8501）\n"
                "2) 关闭其它会加载本项目的 Python / Jupyter\n"
                "3) 关掉资源管理器中打开「向量数据库」文件夹的窗口（含右侧预览窗格）\n"
                "4) 任务管理器中结束仍占用该目录的 python.exe\n"
                f"仍失败可调高等待：环境变量 VECTOR_DB_RESET_MAX_ATTEMPTS、VECTOR_DB_RESET_RETRY_DELAY_SEC"
            ) from last_err
    persist_dir.mkdir(parents=True, exist_ok=True)

