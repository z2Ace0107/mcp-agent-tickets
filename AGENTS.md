# AGENTS.md — AgentForge

> Claude 会话入口。`/clear` 后读此文件恢复上下文。

## 启动

```powershell
cd "E:\develop\claude\项目开发2\LineMind\linemind"
.venv/Scripts/Activate.ps1
streamlit run frontend/app.py   # → http://localhost:8501
```

## 项目定位

**闭环 Agent 执行框架**（不是工单系统）。工单是验证场景，核心是 Agent Loop + Planning + RAG 双通道。

## 架构

```
agent_node → tool_executor → agent_node → END
     ↑              │              │
     └──────────────┘              │ (无 tool_calls 时)
           继续执行                 任务完成
```

- 1 Agent + 12 工具 + RAG 双通道（ChromaDB 向量 + FTS5 → RRF）
- 工具层：断路器/重试/超时 + Python 沙箱（AST 分离 + Plotly 双引擎）
- 50 题评测（Jaccard + 执行成功率 + 步数/耗时）

## 开发流程

1. 改代码 → 重启 Streamlit → 浏览器测
2. `python eval/judge.py -n 10 --seed 42` 快速评测
3. `python eval/bench_rag.py` RAG 回归
4. 发版前：`python eval/judge.py -n 50 -o eval/report.json`

## 关键文件

| 文件 | 职责 |
|------|------|
| `backend/agent_loop.py` | Agent Loop 核心循环（项目灵魂） |
| `backend/tools.py` | 12 工具 + 断路器 + 沙箱 |
| `backend/rag.py` | RAG 双通道检索 |
| `backend/graph.py` | LangGraph 图（极简 3 节点） |
| `backend/prompts.py` | Agent Prompt |
| `frontend/app.py` | Streamlit 流式 UI |
| `eval/judge.py` | 评测脚本 |

## 文档索引

| 文档 | 内容 |
|------|------|
| [PLAN.md](PLAN.md) | 完整项目计划 + 学习路径 |
| [README.md](README.md) | 项目介绍 |
| [CHANGELOG.md](CHANGELOG.md) | 版本记录 |

## 环境变量

```
DEEPSEEK_API_KEY=sk-xxx
BAIDU_API_KEY=bce-v3/ALTAK-xxx
EMBEDDING_API_KEY=sk-xxx
```

## Git

```
当前分支: master
最新 tag: v4.1.0
```
