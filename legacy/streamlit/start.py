"""
启动 Streamlit 时始终使用「当前终端里的 python」。
请先: conda activate langchain_env
勿在 conda base 下对本项目执行 pip install（依赖应只装在 langchain_env）。
"""
import argparse
import os
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _ensure_streamlit_available() -> None:
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print(
            "错误：当前 Python 未安装 streamlit。\n"
            f"  实际使用的解释器：{sys.executable}\n\n"
            "常见原因：用了 Windows 的 `py` 启动脚本，它指向了别的 Python（例如 E:\\python），"
            "而不是已装好依赖的 conda 环境。\n\n"
            "请在本项目目录执行：\n"
            "  conda activate langchain_env\n"
            "  python start.py --kb\n"
            "务必使用命令 `python`，不要使用 `py`。\n",
            file=sys.stderr,
        )
        sys.exit(1)


def _exec_streamlit(target_py: Path, port: int, address: str):
    # 用当前解释器启动，确保走 conda 环境
    python = sys.executable
    args = [
        python,
        "-m",
        "streamlit",
        "run",
        str(target_py),
        "--server.port",
        str(port),
        "--server.address",
        address,
    ]
    os.execv(python, args)


def main():
    parser = argparse.ArgumentParser(description="Start the Streamlit app.")
    parser.add_argument(
        "--kb",
        action="store_true",
        help="Start knowledge base admin UI (default is chat UI).",
    )
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--address", type=str, default="127.0.0.1")

    args = parser.parse_args()

    root = _project_root()
    if args.kb:
        target = root / "app_kb_admin.py"
        port = args.port or 8502
    else:
        target = root / "app_chat.py"
        port = args.port or 8501

    _ensure_streamlit_available()
    _exec_streamlit(target, port=port, address=args.address)


if __name__ == "__main__":
    main()

