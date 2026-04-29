import os
import shutil
import stat
import time
from pathlib import Path
from typing import Optional

from app.core import config

_CHROMA_WRITE_HINT = (
    "常见原因：①「向量数据库」或 chroma.sqlite3 属主为 root，而当前进程为普通用户；"
    "② Docker 挂载卷与容器内 UID 不一致，或卷以 :ro 只读挂载；"
    "③ 另一进程（后端服务、向量构建任务或第二个 uvicorn）正占用同一 chroma.sqlite3。\n"
    "处理建议（在项目根目录的宿主机上执行）：\n"
    "  sudo chown -R \"$USER:$USER\" 向量数据库 && chmod -R u+rwX 向量数据库\n"
    "Docker：确认 compose 中 `./向量数据库:/workspace/向量数据库` 未加 :ro；可先停止 backend 后再构建。\n"
    "仍无法修复时：在 .env 中设置 LAWASK_VECTOR_DB_DIR 为当前用户可写的绝对路径（需与 backend 共用同一变量）。"
)


def _try_chmod_uw(path: Path) -> None:
    """在 Unix 上尽量为属主增加写权限（不抛异常）。"""
    if os.name == "nt" or not path.exists():
        return
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IWUSR)
    except OSError:
        pass


def assert_chroma_persist_dir_writable(persist_dir: Path) -> None:
    """
    Chroma 底层使用 SQLite；若目录或已有 chroma.sqlite3 不可写，会在写入时报
    ``attempt to write a readonly database``。在打开向量库前做探测并给出可操作的错误说明。
    """
    persist_dir = Path(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    if not os.access(persist_dir, os.W_OK):
        raise RuntimeError(f"向量库目录不可写：{persist_dir}\n{_CHROMA_WRITE_HINT}")

    probe = persist_dir / ".lawask_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as e:
        raise RuntimeError(
            f"无法在向量库目录创建文件 {persist_dir}：{e}\n{_CHROMA_WRITE_HINT}"
        ) from e

    for name in ("chroma.sqlite3", "chroma.sqlite3-wal", "chroma.sqlite3-shm"):
        p = persist_dir / name
        if not p.exists():
            continue
        if not os.access(p, os.W_OK):
            _try_chmod_uw(p)
        if not os.access(p, os.W_OK):
            raise RuntimeError(
                f"Chroma SQLite 文件不可写（将导致 readonly database）：{p}\n{_CHROMA_WRITE_HINT}"
            )


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
    persist_dir = Path(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    assert_chroma_persist_dir_writable(persist_dir)

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


def get_kb_chroma_vector_store(collection_dir_name: str):
    """
    用户知识库：每个 KB 使用 VECTOR_DB_DIR 下的独立子目录 + 固定 collection `kb_docs`。
    `collection_dir_name` 与 KnowledgeBase.vector_collection 一致。
    """
    persist_dir = Path(config.VECTOR_DB_DIR) / collection_dir_name
    persist_dir.mkdir(parents=True, exist_ok=True)
    assert_chroma_persist_dir_writable(persist_dir)
    embedding = build_tongyi_embeddings()
    try:
        from langchain_community.vectorstores import Chroma
    except ImportError as e:
        raise RuntimeError("未安装 chromadb / langchain-community，或 Chroma 导入失败。") from e
    return Chroma(
        collection_name="kb_docs",
        persist_directory=str(persist_dir),
        embedding_function=embedding,
    )


def rmtree_persistent_path(target: Path) -> None:
    """
    删除目录树（常用于 Chroma 持久化目录）。
    Windows 下 chroma.sqlite3 常被占用，`rmtree` 会 WinError 32，做多轮短重试。
    """
    target = Path(target)
    if not target.exists():
        return
    last_err = None
    n = config.VECTOR_DB_RESET_MAX_ATTEMPTS
    delay = config.VECTOR_DB_RESET_RETRY_DELAY_SEC
    for attempt in range(n):
        try:
            shutil.rmtree(target)
            last_err = None
            break
        except PermissionError as e:
            last_err = e
            if attempt < n - 1:
                time.sleep(delay)

    if last_err is not None and target.exists():
        raise PermissionError(
            f"无法删除向量库目录：{target} 仍被占用（常见为 chroma.sqlite3 被其它进程打开）。\n"
            "请依次尝试：\n"
            "1) 停止正在运行的后端服务或向量构建任务\n"
            "2) 关闭其它会加载本项目的 Python / Jupyter\n"
            "3) 关掉资源管理器中打开该文件夹的窗口（含右侧预览窗格）\n"
            "4) 任务管理器中结束仍占用该目录的 python.exe\n"
            f"仍失败可调高等待：环境变量 VECTOR_DB_RESET_MAX_ATTEMPTS、VECTOR_DB_RESET_RETRY_DELAY_SEC"
        ) from last_err


def remove_kb_chroma_subdirectory(collection_dir_name: str) -> None:
    """
    删除某个知识库对应的 Chroma 持久化子目录（与 KnowledgeBase.vector_collection 同名）。
    不自动重建目录；下次索引时 get_kb_chroma_vector_store 会 mkdir。
    """
    p = Path(config.VECTOR_DB_DIR) / collection_dir_name
    rmtree_persistent_path(p)


def reset_vector_store(persist_dir: Optional[Path] = None):
    """
    删除持久化目录，下一次会重新从数据构建向量库。
    """
    persist_dir = persist_dir or config.VECTOR_DB_DIR
    rmtree_persistent_path(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    assert_chroma_persist_dir_writable(persist_dir)

