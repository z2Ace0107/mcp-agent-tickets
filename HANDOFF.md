# HANDOFF — LineMind 项目交接

> `/clear` 后读此文件即可恢复全部上下文。

## 启动

```powershell
cd "E:\develop\claude\项目开发2\LineMind\linemind"
& e:\develop\claude\.venv\Scripts\Activate.ps1
streamlit run frontend/app.py
# → http://localhost:8501
```

## 当前状态：v4.0 P0 完成 (2026-05-18)

```
v3.5 ✅ → P0 瘦身 ✅ → P1 打磨 → P2 增强
```

## P0 已完成

| # | 事项 | 文件 | 提交 |
|:---:|------|------|:---:|
| 1 | Reporter 数据优先 | `prompts.py` | ✅ f59047a |
| 2 | 砍 Self-Correction | `graph.py`, `judge.py` | ✅ f59047a |
| 3 | Chat 评分豁免 | `judge.py` | ✅ f59047a |
| 4 | 评测报告简化 | `judge.py` | ✅ f59047a |
| 5 | --seed 参数 | `judge.py` | ✅ f59047a |
| 6 | README v4.0 + Mermaid 架构图 | `README.md` | ✅ 0a4cfc6 |
| 7 | CHANGELOG/AGENTS 同步更新 | `CHANGELOG.md`, `AGENTS.md` | ✅ f59047a |
| 8 | DevQuest README Mermaid 图 | `../DevQuest/README.md` | ✅ 1ff7427 |

## 剩余计划

### P1 — 打磨

| # | 事项 | 说明 |
|:---:|------|------|
| 1 | **录 GIF** | 打开 app，录一段"打字提问 → 进度标签 → 流式输出 + 图表"，放 README 顶部 |
| 2 | **Git tag v4.0.0** | P1 完成后打 tag |
| 3 | **RAG 双通道** | 从 DevQuest 移植 FTS5 + RRF 到 LineMind `rag.py`（~80 行），让复用故事做实 |

### P2 — 增强

| # | 事项 | 说明 |
|:---:|------|------|
| 4 | **流式 thinking 区域** | agent token 也流式输出到折叠区域，解决"前面卡后面快"的体验 |
| 5 | **飞书 Webhook** | Reporter 输出推送飞书群，架构图已预留接口 |

---

## 架构速查

```
用户输入 → supervisor_node(拦截+分类) → Query/Analyze/Knowledge
  → tool_executor(超时/重试/熔断/只读守卫) → Reporter(数据优先) → st.write_stream
```

- 5 Agent（Supervisor + Query + Analyze + Knowledge + Reporter）
- 12 MCP 工具（JSON-RPC 2.0 stdio）
- SQLite 13 表 + ChromaDB 向量检索
- 50 题评测集，路由 90%，工具 80%，0 崩溃

## 评测命令

```bash
# 日常快速迭代（10 题，~4min）
python eval/judge.py -n 10 --seed 42

# 发版全量（50 题，~30min）
python eval/judge.py -n 50 -o eval/report.json
```

## 关键文件

| 文件 | 职责 |
|------|------|
| `backend/graph.py` | LangGraph 状态图 + 流式输出 `run_graph_stream` |
| `backend/agent.py` | Agent 入口，25 行 |
| `backend/tools.py` | 12 MCP 工具 |
| `backend/prompts.py` | 所有 system prompt |
| `backend/nodes/*.py` | 5 Agent 节点 |
| `frontend/app.py` | Streamlit 流式 UI |
| `eval/judge.py` | 自动化评测 |

## 环境变量

```
DEEPSEEK_API_KEY=sk-xxx
BAIDU_API_KEY=bce-v3/ALTAK-xxx
EMBEDDING_API_KEY=sk-xxx     # 阿里百炼
```

## Git

```
0a4cfc6 fix: Mermaid 图引号转义
f59047a v4.0 P0: 瘦身优化
3f74476 v3.5: 流式输出完成
```
