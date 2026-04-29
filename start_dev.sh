#!/usr/bin/env bash
# Linux/macOS/WSL 本地开发启动脚本
set -e

echo "==> 启动开发数据库 (MySQL)..."
docker compose -f docker-compose.dev.yml up -d

echo "==> 等待 MySQL 就绪..."
until docker compose -f docker-compose.dev.yml exec -T mysql mysqladmin ping -h 127.0.0.1 --silent 2>/dev/null; do
  echo "  等待中..."
  sleep 2
done

echo ""
echo "✅ 开发环境准备完成"
echo ""
echo "请在新终端分别运行以下命令："
echo ""
echo "  # 后端"
echo "  cd backend && uvicorn app.main:app --reload --port 8000"
echo ""
echo "  # 前端"
echo "  cd frontend && npm install && npm run dev"
echo "访问地址:"
echo "  React 前端:  http://localhost:3000"
echo "  FastAPI:     http://localhost:8000/api/docs"
