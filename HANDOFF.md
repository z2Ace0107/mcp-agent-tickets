# 交接文档 — MCP 智能工单 Agent 系统 v3.0 → v4.0

## 启动命令

```powershell
cd "E:\develop\claude\项目开发2\MCP智能工单Agent系统\mcp-agent-tickets"
& e:\develop\claude\.venv\Scripts\Activate.ps1
rm data/tickets.db   # 首次或重置时删除旧数据库
streamlit run frontend/app.py
# 浏览器: http://localhost:8501
```

## 项目结构

```
mcp-agent-tickets/
├── .streamlit/config.toml    — 深色主题配置（base="dark"）
├── .env                      — DEEPSEEK_API_KEY + EMBEDDING_API_KEY
├── .env.example              — 环境变量模板
├── requirements.txt          — 依赖（含 ddgs 联网搜索）
├── test_agent.py             — 测试脚本（LLM 测试 + 数据库回退测试）
├── HANDOFF.md                — 本文件
├── frontend/
│   └── app.py                — Streamlit 主前端（v3.0 UI）
├── backend/
│   ├── __init__.py           — init_app() 入口（含 RAG 索引构建）
│   ├── config.py             — Settings 类（pydantic-settings）
│   ├── logger.py             — 日志（logging + 文件轮转）
│   ├── database.py           — SQLite（工单 CRUD + 对话 CRUD + 分组查询 + 置顶）
│   ├── tools.py              — 9 个工具函数（含智能推荐 + 联网搜索）
│   ├── prompts.py            — 所有 Prompt（SYSTEM + PREPROCESS + CHAT + FEW_SHOT）
│   ├── agent.py              — LangChain Agent v3.0（预处理/安全/预算/记忆）
│   ├── mcp_server.py         — MCP stdio 服务器（9 个工具定义）
│   └── rag.py                — ChromaDB 向量检索（阿里云百炼 Embedding）
├── data/                     — tickets.db（运行时生成）
├── chroma_data/              — ChromaDB 持久化
└── logs/                     — 日志文件
```

---

## v3.0 已完成功能（2026-05-12）

### 四大核心能力

| # | 能力 | 实现位置 | 原理 |
|---|------|----------|------|
| 1 | **预处理路由** | `agent.py:_preprocess()` | 入口单次 LLM(t=0) 调 → 意图分类(query/analyze/recommend/search/chat) + 问题改写 + 路由(chat/simple_query/complex) |
| 2 | **安全防护** | `agent.py:_execute_tool()` | 指数退避(200→400→800ms) + 10s 超时 + 连续失败3次熔断 + 优雅降级 |
| 3 | **证据预算** | `agent.py:_trim_tool_result()` | 按工具裁剪(search 1500/query 2000/web 1200字符) + 总预算 5200 字符 |
| 4 | **混合记忆** | `agent.py:_compress_history()` | 超 10 条时 LLM 摘要早期消息 + 保留最近 4 条原文 |

### 路由可视化（前端展示）

| 路由 | 徽标 | 触发条件 |
|------|------|----------|
| `chat` | 💬 直接回复 | 闲聊/问系统能力 |
| `simple_query` | ⚡ 快速查询 | 单一明确意图，2 轮迭代 |
| `complex` | 🧠 深度推理 | 需要多工具编排，5 轮迭代 |

### 推理面板展示

每个 assistant 消息的展开面板内：
- **步骤 0** — 意图识别（意图类别 + 路由决策 + 改写后的问题）
- **步骤 N** — 工具调用，含：⏱ 耗时、📄 字符数、✂ 已裁剪/降级 徽标、🔄 重试次数

### Agent 返回数据结构

```python
{
    "output": str,                    # 最终回复文本
    "intermediate_steps": [
        {
            "thought": str,           # 推理过程
            "action": str,            # 工具名
            "action_input": str,      # 工具参数 JSON
            "observation": str,       # 工具返回（截断至 2000 字符）
            "elapsed": float,         # 工具耗时（秒）
            "original_length": int,   # 原始字符数
            "trimmed": bool,          # 是否被裁剪
            "degraded": bool,         # 是否降级
            "retries": int,           # 重试次数
        }
    ],
    "route": "chat|simple_query|complex",
    "intent": "query|analyze|recommend|search|chat",
    "rewritten_query": str,
    "context_info": {"total_messages": int, "compressed": int, "kept": int} | None,
}
```

### 本会话修复（2026-05-12）

| 修复项 | 说明 |
|--------|------|
| chat 路由徽标不显示 | `route != "chat"` 条件去掉，所有路由都显示徽标 |
| simple_query 无输出结果 | `max_iter` 从 1 改为 2（1 次调工具 + 1 次生成回答） |
| "已裁剪"徽标 HTML 转义 | `st.markdown` 加 `unsafe_allow_html=True` |

---

## v3.1 → v4.0 规划（Super Agent 演进）

完整计划见：`C:\Users\Y7000p\.claude\plans\jolly-weaving-catmull.md`

```
Day 1  v3.1  UI 轻量化        30min   字体/卡片/侧边栏/输入框/表格
Day 1  v3.2  主动智能         2h      一键日报 + 紧急告警 + 实时轮询
Day 2  v3.3  多 Agent 协作    3h      调度/诊断/预警/汇报 四 Agent
Day 3  v3.4  真实系统打通     4h      企微通知 + Cron + IoT 模拟
```

### v3.1 — UI 轻量化（改动 app.py）

1. 字体/行高：全局 14px，对话行高 1.65
2. 统计卡片轻量：保持幽灵风格，数字着色、标签灰色
3. 侧边栏折叠：快捷查工单/提醒/演示 → `st.expander("⚡ 工具箱")`
4. 输入框增强：min-height 60px，focus 阴影
5. 表格 CSS 极简：去竖线，仅底线，表头浅色小字
6. 输出后处理：Markdown 表格 → Key-Value 列表

### v3.2 — 主动智能

- 新建 `backend/scheduler.py` — 定时任务调度
- 新建 `REPORT_PROMPT` — 日报结构模板
- "📊 生成日报" → `recommend_tickets` + `analyze_tickets(summary)` → 格式化
- 紧急告警：≥3 个紧急 OR 超 24h 未分配 → 侧边栏红色
- 实时轮询 toggle：60s 刷新统计

### v3.3 — 多 Agent 协作

```
Orchestrator（路由）
  ├─ Dispatcher Agent → query_tickets, assign_ticket, recommend
  ├─ Diagnoser Agent  → search_solutions, web_search, get_ticket_detail
  ├─ Monitor Agent    → analyze(积压), recommend(异常)
  └─ Reporter Agent   → 多工具聚合 + 格式化
```

面试标准答案：
> "单 Agent 有三个瓶颈：Prompt 随工具变长 → 指令精度下降；诊断要深度推理、调度要快速决策 → 单 Agent 难兼顾；权限边界模糊。专职 Agent 各拥工具子集 + System Prompt，token 更省、响应更快、权限更清晰。"

### v3.4 — 真实系统打通

- `notify_wechat(webhook_url, content)` 工具
- `query_device_status(device_id)` 模拟 IoT
- Cron 持久化到 `.claude/scheduled_tasks.json`
- MCP 工具热注册

---

## 关键设计决策

- **Agent 模式**: LangChain `llm.bind_tools()` 手动循环，不用 `AgentExecutor`
- **LLM**: DeepSeek v4-flash，OpenAI 兼容 API，关闭 thinking
- **Embedding**: 阿里云百炼 `text-embedding-v3`
- **主题**: Streamlit 原生深色（base="dark"），CSS 覆盖为 `#1b1c21` DeepSeek 风格
- **预处理温度**: t=0（确保分类稳定），chat 模式 t=0.1
- **simple_query max_iter=2**: 第 1 轮调工具，第 2 轮生成回答
- **complex max_iter=5**: 多步工具编排

## 数据库 Schema

```sql
tickets (id, ticket_id, title, type, status, priority, assignee, created_at, updated_at, description)
ticket_replies (id, ticket_id, content, created_at)
conversations (id, title, created_at, updated_at, pinned)
conversation_messages (id, conversation_id, role, content, steps, created_at)
```

## 种子数据

20 条真实工厂工单：设备故障×5 / 质量异常×4 / 安全隐患×3 / 物料短缺×2 / 工艺问题×2 / 生产计划×2 / 环境监测×2

---

## Git 信息

- **仓库**: https://github.com/z2Ace0107/mcp-agent-tickets
- **远程**: `git@github.com:z2Ace0107/mcp-agent-tickets.git`
- **分支**: master

## 测试命令

```powershell
python test_agent.py                           # CLI 测试
streamlit run frontend/app.py                  # UI 测试
python backend/mcp_server.py                   # MCP Server 测试
```
