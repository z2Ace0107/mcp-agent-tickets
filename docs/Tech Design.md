# Tech Design: Super Agent — 基于 MCP 的多智能体工业协管平台

> **版本**: v3.0 | **更新日期**: 2026-05-12
>
> 本文档记录当前实际架构。项目从 MVP（2 工具 + 单 Agent）演进而来，原始技术设计见文末附录。

---

## 1. 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                    Streamlit 前端                        │
│  路由徽标 / 步骤0意图识别 / 工具耗时 / 证据裁剪标记       │
└──────────────┬───────────────────────────────────────────┘
               │ asyncio.run(run_agent())
               ▼
┌──────────────────────────────────────────────────────────┐
│                    Agent 核心层                           │
│                                                          │
│  run_agent()                                             │
│    ├─ _preprocess()       ← 意图分类 + 改写 + 路由       │
│    ├─ _compress_history() ← 早期消息 LLM 摘要压缩        │
│    ├─ _execute_tool()     ← 重试/超时/熔断/裁剪          │
│    └─ _extract_intermediate_steps() ← 含元信息提取       │
└──────┬────────────────────┬──────────────────────────────┘
       │                    │
       ▼                    ▼
┌──────────────┐    ┌──────────────────┐
│  工具层 (9)   │    │   知识层          │
│              │    │                  │
│ query_tickets│    │ ChromaDB         │
│ analyze      │    │ (阿里百炼        │
│ update_status│    │  text-embed-3)   │
│ assign       │    │                  │
│ add_reply    │    │ RAG 检索         │
│ get_detail   │    │ 7 条已解决工单   │
│ search_sol   │    │                  │
│ recommend    │    │                  │
│ web_search   │    │                  │
└──────┬───────┘    └──────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│                    数据持久层                             │
│                                                          │
│  SQLite (tickets.db)                                     │
│  ├─ tickets (20 条种子数据)                               │
│  ├─ ticket_replies                                       │
│  ├─ conversations                                        │
│  └─ conversation_messages                                │
└──────────────────────────────────────────────────────────┘
```

---

## 2. 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| LLM | DeepSeek v4-flash | OpenAI 兼容 API，关闭 thinking |
| Embedding | 阿里云百炼 text-embedding-v3 | ChromaDB 向量化 |
| Agent 框架 | LangChain `llm.bind_tools()` | 手动工具调用循环，不用 AgentExecutor |
| 前端 | Streamlit | 深色主题（#1b1c21），820px 阅读宽度 |
| 数据库 | SQLite | 工单 + 对话持久化 |
| 向量库 | ChromaDB | 持久化，7 条已解决工单索引 |
| 联网搜索 | DuckDuckGo（ddgs 包） | 轻量，无需 API Key |
| 配置 | pydantic-settings + .env | API Key、模型参数、路径 |
| 日志 | logging + RotatingFileHandler | 文件轮转 |
| MCP 协议 | JSON-RPC stdio | 9 个工具暴露 |

---

## 3. 目录结构

```
mcp-agent-tickets/
├── .streamlit/config.toml        — 深色主题（base="dark"）
├── .env / .env.example           — API Key + 配置
├── requirements.txt              — 含 ddgs、schedule
├── test_agent.py                 — CLI 测试脚本
├── frontend/
│   └── app.py                    — Streamlit v3.0 UI（路由徽标+步骤0+耗时）
├── backend/
│   ├── __init__.py               — init_app() 入口（RAG 索引构建）
│   ├── config.py                 — Settings 类
│   ├── logger.py                 — 日志系统
│   ├── database.py               — SQLite CRUD + 对话管理 + 置顶
│   ├── tools.py                  — 9 个工具函数
│   ├── prompts.py                — SYSTEM + PREPROCESS + CHAT + FEW_SHOT
│   ├── agent.py                  — v3.0 Agent（预处理/安全/预算/记忆）
│   ├── mcp_server.py             — MCP stdio 服务器
│   └── rag.py                    — ChromaDB + 阿里百炼 Embedding
├── data/tickets.db               — 运行时生成
├── chroma_data/                  — ChromaDB 持久化
└── logs/                         — 日志文件
```

---

## 4. Agent 设计

### 4.1 预处理路由

用户输入 → 单次 LLM 调用（t=0）→ JSON 输出：

```
{
  "intent": "query|analyze|recommend|search|chat",
  "rewritten_query": "结合对话历史补全的完整问题",
  "route": "chat|simple_query|complex"
}
```

| 路由 | 迭代数 | 处理方式 |
|------|--------|----------|
| chat | 0 | 直接 LLM 回复，不走工具 |
| simple_query | 2 | 1 轮工具调用 + 1 轮生成回答 |
| complex | 5 | 完整 ReAct 循环 |

### 4.2 安全防护

- **指数退避**: 200ms → 400ms → 800ms
- **超时**: 10s（ThreadPoolExecutor + future.result(timeout)）
- **熔断**: 同一工具连续失败 3 次 → 本轮跳过，返回降级 JSON
- **降级**: 失败返回 `{"error": "...", "degraded": true}` 而非异常

### 4.3 证据预算

| 工具 | 裁剪上限 |
|------|---------|
| search_solutions | 1500 字符 |
| query_tickets | 2000 字符 |
| web_search | 1200 字符 |
| 其他 | 2500 字符 |
| 总预算 | 5200 字符（超 80% 警告） |

### 4.4 混合记忆

- 滑动窗口 ≤ 10 条
- 超 10 条时 LLM 将早期消息压缩为 2-3 句摘要
- 保留最近 4 条原文
- 摘要作为 SystemMessage 注入

### 4.5 工具执行元信息

每个 intermediate_step 携带：`elapsed`（秒）、`original_length`（字符）、`trimmed`（布尔）、`degraded`（布尔）、`retries`（整数）

---

## 5. 工具矩阵（9 个）

| # | 工具 | 参数 | 用途 |
|---|------|------|------|
| 1 | query_tickets | ticket_type?, status?, date_range? | 按条件筛选工单 |
| 2 | analyze_tickets | analysis_type | 统计分析（分布/趋势/汇总） |
| 3 | update_ticket_status | ticket_id, new_status | 更新状态 |
| 4 | assign_ticket | ticket_id, assignee | 分配处理人 |
| 5 | add_ticket_reply | ticket_id, content | 添加回复 |
| 6 | get_ticket_detail | ticket_id | 工单详情 + 回复记录 |
| 7 | search_solutions | query | RAG 检索历史方案 |
| 8 | recommend_tickets | — | 智能推荐（紧急+积压+分配+关联） |
| 9 | web_search | query | DuckDuckGo 联网搜索 |

---

## 6. 数据模型

```sql
tickets (id, ticket_id, title, type, status, priority, assignee, created_at, updated_at, description)
ticket_replies (id, ticket_id, content, created_at)
conversations (id, title, created_at, updated_at, pinned)
conversation_messages (id, conversation_id, role, content, steps, created_at)
```

种子数据：20 条真实工厂工单 — 设备故障×5 / 质量异常×4 / 安全隐患×3 / 物料短缺×2 / 工艺问题×2 / 生产计划×2 / 环境监测×2

---

## 7. 关键技术决策

### 为什么用 `llm.bind_tools()` 而非 `initialize_agent`？

LangChain 的 `AgentExecutor` 是不透明黑盒，无法控制工具调用循环、无法插入预处理/熔断/证据预算逻辑。`bind_tools()` + 手动循环提供了完全的控制权，且代码量差不多。

### 为什么 RAG 用 API Embedding 而非本地模型？

阿里云百炼 `text-embedding-v3` 在中文工业文本上的表现优于开源轻量模型，且无需 GPU。对于 20 条工单的规模，API 延迟 < 200ms，性价比远高于维护本地模型服务。

### 为什么拆分为 4 个专职 Agent 而非单 Agent？

单 Agent 有三个瓶颈：
1. System Prompt 随工具增多变长，影响指令遵循精度
2. 诊断要深度推理链、调度要快速决策 — 单 Agent 难兼顾不同思考模式
3. 工具权限集中，安全边界模糊

专职 Agent 各拥工具子集 + 特定 System Prompt，token 更省、响应更快、权限清晰。单个 Agent 替换模型不影响其他。

### 为什么用 schedule 而非 Celery/Redis？

当前规模（单用户、本地运行）不需要消息队列。`schedule` 是进程内定时库，零依赖，适合轮询巡检。未来多用户场景可平滑迁移到 Celery。

### 为什么用 Streamlit 而非 React/Next.js？

目标是用 Python 全栈快速验证 Agent 架构，而非打磨前端。Streamlit 的开发效率（一个文件）是 React 的 5-10 倍。面试时说明这是"架构验证阶段的工具选择"，展现务实判断力。

### 为什么用 DuckDuckGo 而非 Google/Bing API？

零 API Key、零配额限制，适合 demo 场景。对于工单系统中偶尔需要外部技术资料的场景，DDG 的覆盖度足够。

---

## 附录: 原始 MVP 技术设计（v1.0）

> 以下为项目起点（2026-05-08）的原始技术设计，保留用于展示演进过程。

- 架构: Streamlit → LangChain Agent (ReAct) → MCP 工具服务器 → 模拟数据
- 工具: 2 个（query_tickets、analyze_tickets）
- 模拟数据: 15 条
- Agent 模式: ReAct，temperature=0
- 错误处理: 解析错误自动重试（最多 3 次）
