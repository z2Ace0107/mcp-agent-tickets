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

## 当前状态：v3.3 + 今日修复 (2026-05-17) ✅

```
v2.0 ✅ → v3.1 ✅ → v3.2 ✅ → v3.3 ✅ → 今日批量修复 ✅
```

**今日修复（7项）：**

| # | 问题 | 涉及文件 |
|---|------|----------|
| 1 | DDGS 联网搜索超时4分钟 | tools.py, config.py, graph.py, .env, requirements.txt |
| 2 | matplotlib 未安装，图表功能不可用 | tools.py, requirements.txt |
| 3 | Python 沙箱 print() 从未被捕获 (sys.stdout bug) | tools.py |
| 4 | Query/Analyze Agent 绕过高层工具直接用 SQL/Python | prompts.py (两处) |
| 5 | "你好"走完整 LLM 管线 | supervisor.py |
| 6 | 推理面板展开跳到底部 + 无法一键折叠 | app.py (MutationObserver) |
| 7 | 图表生成后前端不显示 (Reporter 内联路径丢弃 chart_images) | reporter.py, app.py |

## 环境变量

```
DEEPSEEK_API_KEY=sk-xxx
BAIDU_API_KEY=bce-v3/ALTAK-xxx      # 百度AI搜索，100次/天免费
BAIDU_SEARCH_BASE_URL=https://qianfan.baidubce.com/v2/ai_search
EMBEDDING_API_KEY=sk-xxx             # 阿里百炼
```

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

## 已知架构弱点

**Reporter 内联执行 vs tool_executor_node 双路径**：Reporter 的 `execute_python` 在 `reporter_node` 内联执行，不经过 `tool_executor_node`。这意味着 tool_executor_node 的步骤记录、超时控制、熔断器等机制对 Reporter 路径无效。改代码时如果只改了一个路径，bug 会在另一个路径复现。

**性能**：当前"画工单类型分布图"耗时 ~42s（5次 LLM 调用 + Python 图表生成）。瓶颈在 analyze agent 的多轮 tool call 往返。

## 手动测试

```powershell
streamlit run frontend/app.py
```

| 输入 | 检查点 |
|------|--------|
| 查看所有工单 | 推理用 `query_tickets`，非 `execute_sql` |
| 统计工单类型数量 | 推理用 `analyze_tickets`，非 `execute_python` |
| 画工单类型分布图 | 图表直接显示在回复中，中文不乱码 |
| 搜索工厂设备维修方案 | `联网搜索` 几秒内返回 |
| 你好 | 简短回复，推理面板显示"💬 直接回复" |
| 展开"推理过程" | 不跳底，底部有"收起 ▲"可折叠 |

## 待改进

### P0: 架构统一 — Reporter 工具执行走 tool_executor_node
Reporter 的 execute_python 应通过 tool_executor_node 执行，消除双路径。改动 graph.py 路由逻辑 + reporter_node。

### P1: 流式输出
当前全量生成后渲染，用户等 30s+。用 LangGraph `astream` + `st.write_stream`。

### P1: 性能优化
analyze agent 多轮往返是主要瓶颈。考虑：合并 analyze_tickets + recommend_tickets 为单次调用，限 MAX_AGENT_ITERATIONS=3。

### P2: 可观测性
LangSmith Tracing + 评测集
