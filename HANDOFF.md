# HANDOFF — Super Agent 项目交接

> `/clear` 后读此文件即可恢复全部上下文。

## 启动

```powershell
cd "E:\develop\claude\项目开发2\MCP智能工单Agent系统\mcp-agent-tickets"
& e:\develop\claude\.venv\Scripts\Activate.ps1
rm data/tickets.db -ErrorAction SilentlyContinue   # 首次或重置
streamlit run frontend/app.py
# → http://localhost:8501
```

## 当前状态：v3.3 完成 ✅

```
v2.0 ✅ → v3.1 ✅ → v3.2 ✅ → v3.3 ✅ → v3.4 → v4.0
```

（第一轮 v3.3 已回退 commit 0cbbb0e，当前为第二轮重做 commit 80d82a9）

## v3.3 架构

```
Supervisor(路由) → {Query(6工具) | Analyze(3) | Knowledge(3)} → Reporter(execute_python)
    ↑                                                                    │
    └────────── tool_executor ← Self-Correction(SQL出错→修正→重试) ←────┘
```

### 数据层：12 张表

| 表 | 作用 | 数据量 |
|----|------|--------|
| tickets | 工单事实表（含 equipment_id/line_id/material_id FK） | 30 条 |
| equipment | 设备维度 | 10 条 |
| production_lines | 产线维度 | 4 条 |
| materials | 物料维度 | 6 条 |
| quality_metrics | 质量指标 | 3 条 |
| ticket_replies | 工单回复 | 0 |
| conversations / conversation_messages | 对话历史 | 0 |
| db_schema_info | Schema 元数据 | 72 条 |
| agent_actions | Agent 操作日志 | 0 |
| sql_templates | SQL 模板 | 8 条 |
| correction_rules | 自校正规则 | 7 条 |

### Agent 节点

| Agent | 文件 | 工具 |
|-------|------|------|
| Supervisor | `backend/nodes/supervisor.py` | 无（LLM t=0 分类） |
| Query | `backend/nodes/query.py` | execute_sql, get_schema, query_tickets, get_ticket_detail, update_ticket_status, assign_ticket |
| Analyze | `backend/nodes/analyze.py` | analyze_tickets, execute_python, recommend_tickets |
| Knowledge | `backend/nodes/knowledge.py` | search_solutions, web_search, get_ticket_detail |
| Reporter | `backend/nodes/reporter.py` | execute_python（图表生成） |

### 12 个 MCP 工具

query_tickets / analyze_tickets / update_ticket_status / assign_ticket / add_ticket_reply / get_ticket_detail / search_solutions / recommend_tickets / web_search / get_schema / execute_sql / execute_python

## 项目结构（v3.3）

```
mcp-agent-tickets/
├── frontend/app.py              — Streamlit UI（重置12表）
├── backend/
│   ├── __init__.py              — init_app() 入口
│   ├── config.py                — Settings
│   ├── logger.py                — 日志
│   ├── database.py              — SQLite（12表 + 种子数据）
│   ├── tools.py                 — 12 工具实现
│   ├── prompts.py               — 全部 Prompt（含5个Agent专用）
│   ├── agent.py                 — run_agent() 入口（25行）
│   ├── graph.py                 — LangGraph StateGraph + 工具子集定义 + run_graph()
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── supervisor.py        — 意图分类 + 路由
│   │   ├── query.py             — Query Agent
│   │   ├── analyze.py           — Analyze Agent
│   │   ├── knowledge.py         — Knowledge Agent
│   │   └── reporter.py          — Reporter（内联执行 execute_python）
│   ├── scheduler.py             — v3.2 告警检测 + 日报生成
│   ├── rag.py                   — ChromaDB 向量检索
│   └── mcp_server.py            — MCP stdio 服务器（12工具）
├── test_agent.py                — CLI 测试（6 LLM 用例 + 14 DB 用例）
├── CHANGELOG.md / README.md
└── .env / requirements.txt
```

## 验证方式

```powershell
rm data/tickets.db
python test_agent.py                 # 6 LLM 用例 + 14 DB 用例
streamlit run frontend/app.py        # UI 黄金路径 + 重置12表
```

### 手动测试关键用例

| 输入 | 预期路由 |
|------|----------|
| 最近一周有哪些设备故障工单？ | Query Agent |
| 帮我分析这个月工单趋势 | Analyze Agent |
| 查看工单 WO-20260428-001 详情 | Query Agent |
| 曲轴淬火变形率超标怎么办？ | Knowledge Agent |
| 帮我分析工单优先级和紧急程度 | Analyze Agent |
| 你好 | Reporter (chat) |

展开"推理过程"面板 → 步骤 0 显示路由 → 后续步骤工具名匹配 Agent 职责

---

## v3.3 待改进（下个 /clear 后优先）

### 1. Reporter execute_python 触发优化

当前 Reporter 绑了 execute_python，但触发条件不明确。
**方案**：改 `REPORTER_PROMPT`，加规则——"当用户要求图表/可视化/柱状图/趋势图，或统计数据超过 5 行时，用 execute_python 生成图表代码"。不改代码。

### 2. 流式输出

当前 `st.chat_message` 等全部生成完再渲染，用户等待 30s+。
**方案**：graph.py 加 `run_graph_stream()`，用 LangGraph `astream` + Streamlit `st.write_stream`。

### 3. v3.4：可观测性 + 评测（见 AGENTS.md）

- LangSmith Tracing（环境变量 `LANGCHAIN_TRACING_V2=true`）
- 50 条测试集 + LLM-as-a-judge 自动评分
