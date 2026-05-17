# HANDOFF — LineMind 项目交接

> `/clear` 后读此文件即可恢复全部上下文。

## 启动

```powershell
cd "E:\develop\claude\项目开发2\LineMind\linemind"
& e:\develop\claude\.venv\Scripts\Activate.ps1
rm data/tickets.db -ErrorAction SilentlyContinue   # 首次或重置
streamlit run frontend/app.py
# → http://localhost:8501
```

## 当前状态：v3.3 + 修复 → v3.4 开发中 (2026-05-17)

```
v3.3 ✅ → 今日修复(8项) ✅ → v3.4 (CURRENT) → v4.0
                              ├─ 评测50题       ├─ 流式输出
                              ├─ LangSmith      ├─ README大改
                              └─ 量化数据       ├─ GIF演示
                                               └─ 收尾发布
```

**今日修复（8项）：**

| # | 问题 | 涉及文件 |
|---|------|----------|
| 1 | DDGS 联网搜索超时4分钟 | tools.py, config.py, graph.py, .env, requirements.txt |
| 2 | matplotlib 未安装，图表功能不可用 | tools.py, requirements.txt |
| 3 | Python 沙箱 print() 从未被捕获 (sys.stdout bug) | tools.py |
| 4 | Query/Analyze Agent 绕过高层工具直接用 SQL/Python | prompts.py (两处) |
| 5 | "你好"走完整 LLM 管线 | supervisor.py |
| 6 | 推理面板展开跳到底部 + 无法一键折叠 | app.py (MutationObserver) |
| 7 | 图表生成后前端不显示 (Reporter 内联路径丢弃 chart_images) | reporter.py, app.py |
| 8 | plt.savefig 污染项目根目录（10 张 PNG） | tools.py + .gitignore |

## 文档结构（整理后）

```
项目根/
├── AGENTS.md          ← 主线开发文档（版本规划+面试要点）
├── linemind/
│   ├── HANDOFF.md     ← 本文件（启动+架构+状态）
│   ├── README.md      ← 对外展示（v3.0 过时，v4.0 重写）
│   ├── CHANGELOG.md   ← 版本记录
│   ├── docs/          ← 已清空（旧 PRD/Tech Design 已删）
│   └── eval/          ← 评测脚本（v3.4 新建）
```

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
linemind/
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

## v3.4 计划 — 评测体系

| 类别 | 题数 | 说明 |
|------|------|------|
| 工单查询 (Query) | 12 | 按类型/状态/日期/优先级筛选 |
| 统计分析 (Analyze) | 12 | 分布/趋势/汇总/对比 |
| 知识检索 (Knowledge) | 8 | 内部 RAG + 联网搜索 |
| 工单操作 (Action) | 8 | 更新状态/分配/回复 |
| 综合推理 (Multi-hop) | 6 | 多 Agent 协作/多步推理 |
| 闲聊拦截 (Chat) | 4 | 问候/无关话题 |
| **总计** | **50** | |

评测维度：工具选择准确率 / Agent 路由准确率 / SQL 执行成功率 / Self-Correction 成功率 / 回答相关性(1-5)

## v4.0 计划 — 展示包装

- 流式输出：graph.astream + st.write_stream
- README v4.0：架构图 + GIF + 评测数据
- P0 架构统一：Reporter 走 tool_executor_node
- 收尾发布：git tag v4.0.0
