FROM python:3.11-slim

WORKDIR /workspace

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libssl-dev curl \
    && rm -rf /var/lib/apt/lists/*

# 安装后端依赖（RAG 核心已内聚到 backend/app）
COPY ./backend/requirements.txt /workspace/backend/requirements.txt

RUN pip install --no-cache-dir -r /workspace/backend/requirements.txt

# 复制项目
COPY . /workspace/

WORKDIR /workspace/backend

ENV PYTHONPATH=/workspace/backend
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
