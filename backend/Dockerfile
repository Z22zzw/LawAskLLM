FROM python:3.11-slim

WORKDIR /workspace

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libssl-dev curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制根目录 RAG 模块
COPY ./requirements.txt /workspace/requirements.txt
COPY ./backend/requirements.txt /workspace/backend_requirements.txt

RUN pip install --no-cache-dir -r /workspace/requirements.txt \
    && pip install --no-cache-dir -r /workspace/backend_requirements.txt

# 复制项目
COPY . /workspace/

WORKDIR /workspace/backend

ENV PYTHONPATH=/workspace
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
