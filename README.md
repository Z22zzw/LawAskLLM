# 法律RAG智能问答（Streamlit + LangChain + Chroma）



## 运行环境（重要）



本项目依赖**只应**安装在 Conda 环境 **`langchain_env`** 中，**不要**在 `base` 里 `pip install` 本项目的包。



```powershell

conda activate langchain_env

cd e:\corsur\cursor_workspace\test_1

python -m pip install -r requirements.txt

```



自检（路径中应出现 `envs\langchain_env`）：



```powershell

python -c "import sys; print(sys.executable)"

python -m pip -V

```



Cursor / VS Code：已提供 [`.vscode/settings.json`](.vscode/settings.json) 指向 `langchain_env` 的解释器；若你的 Miniconda 安装路径不同，请修改其中的 `python.defaultInterpreterPath`。



不激活环境时，可用（路径按你机器上的 conda 安装位置调整）：



```powershell

conda run -n langchain_env python -m pip install -r requirements.txt

conda run -n langchain_env python start.py

```



---



## 项目做什么



基于 **RAG** 的法律问答：Chroma 向量库 + 通义嵌入 + OpenAI 兼容接口大模型（如 DeepSeek）+ Streamlit 界面；会话可选 **MySQL** 持久化（失败则内存降级）。

### 法律领域与页面分工

- **知识库构建页**：选择入库数据源、全量重建、调试条数；并配置 **对话页默认检索策略**（`balanced` / `auto` / 单源、是否 MMR、是否默认 Agent），保存为项目根目录 **`runtime_rag_prefs.json`**。
- **对话页**：用户只选 **法律领域 Agent**（刑法、民法、综合等）。检索时按 `metadata.legal_domain` 过滤；**综合**不按领域过滤。
- 领域标签在 **`legal_domain_map.py`** 中由 JEC 的 `subject` 规则映射；CAIL 统一标为刑法。**首次启用或修改映射后请全量重建向量库**，否则旧数据无 `legal_domain` 字段，过滤结果可能为空。

---



## 目录与模块（梳理）



| 路径 | 作用 |

|------|------|

| `config.py` | 路径、API、MySQL、检索参数；`LEGAL_DOMAIN_CHOICES` / `LEGAL_DOMAIN_LABELS`；`RUNTIME_RAG_PREFS_PATH` |

| `vector_store_service.py` | Chroma + DashScope 嵌入 |

| `kb_update_service.py` | JEC-QA / CAIL2018 读入、切块、写入向量库；写入 `metadata.legal_domain` |

| `legal_domain_map.py` | 科目/罪名 → 法律领域短码；对话页领域列表 |

| `rag_prefs.py` | 读写 `runtime_rag_prefs.json`（数据源策略、MMR、Agent 默认） |

| `rag_service.py` | **LCEL 链**；按领域 + prefs 检索；`retrieve_documents`、`rag_chain` |

| `rag_agent.py` | **LangChain Agent** + `search_legal_kb`（带 `legal_domain`）；失败回退 `rag_chain` |

| `memory_store.py` | MySQL / 内存 会话与消息 |

| `app_chat.py` | 对话页：仅选法律领域 Agent；链式步骤与依据展示 |

| `app_kb_admin.py` | 向量库构建 + 保存 `runtime_rag_prefs.json` |

| `start.py` | 用**当前解释器**拉起 Streamlit（保证走已激活的 conda 环境） |

| `data/` | 数据集（JEC-QA、CAIL2018） |

| `向量数据库/` | Chroma 持久化目录 |

| `历史聊天信息存储/` | 会话导出 jsonl |



---



## 近期功能改动摘要（相对最初版）



- **双数据集检索**：`source_mode`（auto / balanced / jec_only / cail_only）、双路均衡合并、可选 **MMR**（策略在知识库页保存）。

- **法律领域**：入库写 `legal_domain`；对话页选领域 Agent 过滤检索；映射见 `legal_domain_map.py`。

- **链式流程**：`RunnableLambda` + `RunnableBranch`；法律支路含**澄清引导**。

- **Agent 模式**：`create_agent` + `search_legal_kb`（默认开关在知识库页）。

- **前端**：双栏、指标、链式追踪、示例问题、依据卡片。

- **知识库页**：构建 + `runtime_rag_prefs.json`；双源全量重建时仅首次清空向量目录。



---



## 环境变量（推荐系统环境变量）



模板见 `.env.template`。程序**默认不自动读 `.env`**，需系统/用户环境变量或自行加载。



### Tongyi/DashScope Embeddings

- `DASHSCOPE_API_KEY`



### LLM（OpenAI 兼容接口）

- `LLM_API_KEY`

- `LLM_BASE_URL`（例如 `https://dashscope.aliyuncs.com/compatible-mode/v1`）

- `LLM_MODEL`（例如 `deepseek-v3.2`）



### MySQL（可选）

- `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DB`



### 检索（可选）

- `RETRIEVAL_USE_MMR`、`RETRIEVAL_MMR_FETCH_K`、`RETRIEVAL_MMR_LAMBDA`



---



## 构建向量库



```powershell

conda activate langchain_env

python start.py --kb

```



或：`streamlit run app_kb_admin.py`（端口默认见下）。



---



## 运行对话



```powershell

conda activate langchain_env

python start.py

```



## 常用端口

- 聊天：`8501`

- 知识库管理：`8502`



## 启动参数

- 默认聊天：`python start.py`

- 知识库：`python start.py --kb`

- 自定义端口：`python start.py --port 8600`；知识库：`python start.py --kb --port 8601`


