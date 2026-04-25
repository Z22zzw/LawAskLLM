# 法律 LLM 平台 — Makefile（兼容 Linux/macOS/Windows Git Bash）
.PHONY: help dev dev-db backend frontend build up down logs

help:
	@echo ""
	@echo "  make dev        本地开发（仅启 MySQL，前后端分别运行）"
	@echo "  make dev-db     仅启动开发用 MySQL"
	@echo "  make backend    启动 FastAPI 后端（需先激活 Python 环境）"
	@echo "  make frontend   启动 React 前端（Vite dev server）"
	@echo "  make build      构建生产镜像"
	@echo "  make up         生产模式启动所有服务"
	@echo "  make down       停止所有服务"
	@echo "  make logs       查看生产容器日志"
	@echo ""

dev-db:
	docker compose -f docker-compose.dev.yml up -d

backend:
	cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

dev: dev-db
	@echo "MySQL 已启动。请在两个终端分别运行:"
	@echo "  make backend"
	@echo "  make frontend"

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=100
