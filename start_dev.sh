#!/usr/bin/env bash
# Linux/macOS/WSL 本地开发启动脚本
set -e

echo "==> 启动开发数据库 (MySQL)..."
docker compose -f docker-compose.dev.yml up -d

echo "==> 等待 MySQL 就绪..."
sleep 5

echo ""
echo "✅ 开发环境准备完成"
echo ""
echo "请在新终端分别运行以下命令："
echo ""
echo "  # 后端 (需要 langchain_env conda 环境)"
echo "  conda activate langchain_env"
echo "  cd backend && uvicorn app.main:app --reload --port 8000"
echo ""
echo "  # 前端"
echo "  cd frontend && npm install && npm run dev"
echo ""
echo "  # 旧版 Streamlit (可选)"
echo "  python start.py"
echo ""
echo "访问地址:"
echo "  React 前端:  http://localhost:3000"
echo "  FastAPI:     http://localhost:8000/api/docs"
echo "  Streamlit:   http://localhost:8501"
