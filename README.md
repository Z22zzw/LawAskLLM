# LawAskLLM 法律 RAG 智能问答系统

本项目是基于 **React + FastAPI + LangChain + Chroma** 的法律问答系统。系统提供登录认证、法律对话、知识库管理、数据集向量构建与实验对照能力，RAG 核心已经内聚到后端包内。

## 目录结构

| 路径 | 作用 |
|---|---|
| `backend/app/api/` | FastAPI 路由：认证、用户、对话、知识库、数据集构建、实验对照 |
| `backend/app/core/` | 后端配置、环境变量、全局路径 |
| `backend/app/rag/` | RAG 核心：意图路由、检索、生成、Agent、流式回调、偏好配置 |
| `backend/app/knowledge/` | Chroma 向量库、数据集入库、用户知识库索引 |
| `backend/app/experiments/` | 实验预设、对照执行、评分分析、日志记录 |
| `backend/app/models/` | SQLAlchemy 数据模型 |
| `backend/app/schemas/` | Pydantic 请求/响应模型 |
| `frontend/` | React + Vite 前端 |
| `docs/` | 论文、需求、设计、实验题单等文档 |
| `deploy/` | 服务器部署配置 |
| `scripts/` | 启停、部署、日志脚本 |
| `tools/` | 离线实验日志分析工具 |
| `legacy/streamlit/` | 旧版 Streamlit 代码归档，不再作为主运行入口 |

## 快速启动

1. 复制环境变量模板：

```bash
cp .env.example .env
```

2. 填写 `.env` 中的 `LLM_API_KEY`、`DASHSCOPE_API_KEY`、`MYSQL_PASSWORD` 等配置。

3. 启动全栈服务：

```bash
./scripts/lawask-up.sh
```

常用入口：

- 前端登录：`/login`
- 对话页面：`/chat`
- 知识库管理：`/kb`
- 实验对照：`/experiments`
- API 文档：`/api/docs`

## 本地开发

后端：

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

## 数据与运行时目录

- `data/`：JEC-QA、CAIL2018 等数据集。
- `向量数据库/`：默认 Chroma 持久化目录。可用 `LAWASK_VECTOR_DB_DIR` 指向其他路径。
- `uploads/`：用户知识库上传文件。
- `实验记录/`：实验日志和会话复盘导出。
- `runtime_rag_prefs.json`：RAG 运行时策略偏好。

## 实验功能

实验预设位于 `backend/app/experiments/design.py`，前端实验页通过 `/api/v1/experiments/compare` 对同一问题并行运行多个方案，支持基线对比、检索策略对比与消融实验。

推荐论文实验组合：

- 基线对比：`baseline_llm_direct`、`baseline_rag_basic`、`system_full`
- 检索策略：`strategy_auto`、`strategy_balanced`、`strategy_jec_only`、`strategy_cail_only`
- 消融实验：`system_full`、`ablation_no_mmr`、`ablation_no_rrf`、`ablation_no_evidence_label`、`ablation_no_agent_fallback`

