# MCP 智能工单 Agent 系统 v2.0

基于 **MCP 协议** 的企业级 AI Agent 系统，集成 **RAG 知识库**，支持工单查询、分析、操作与智能解决方案推荐。

> **v2.0 新增**：SQLite 持久化 · 真 MCP 协议 (stdio) · 7 个工具 · RAG 解决方案检索 · 结构化日志 · 多工具自主编排

## 功能

| 类别 | 工具 | 说明 |
|:---|:---|:---|
| 🔍 查询 | `query_tickets` | 按类型/状态/日期筛选工单 |
| 📊 分析 | `analyze_tickets` | 类型分布 / 状态统计 / 优先级 / 趋势 / 汇总 |
| ✏️ 操作 | `update_ticket_status` | 更新工单状态 |
| 👤 分配 | `assign_ticket` | 分配工单给处理人 |
| 💬 回复 | `add_ticket_reply` | 为工单添加回复记录 |
| 📋 详情 | `get_ticket_detail` | 查看工单完整信息 + 回复历史 |
| 🧠 RAG | `search_solutions` | 向量检索历史解决方案，推荐相似案例 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
```

### 3. 启动

```bash
# 前端聊天界面
streamlit run frontend/app.py

# MCP 工具服务器（stdio 模式，可接入 Claude Desktop 等客户端）
python -m backend.mcp_server
```

### Docker

```bash
docker build -t mcp-agent-tickets .
docker run -p 8501:8501 -e DEEPSEEK_API_KEY="your-key" mcp-agent-tickets
```

## 架构

```
用户 → Streamlit 前端
         │
         ▼
    Agent 核心 (llm.bind_tools × 7)
         │
         ├─→ tools.py ──→ SQLite (tickets + replies)
         │
         ├─→ rag.py ──→ ChromaDB 向量检索
         │
         └─→ DeepSeek API (chat + embedding)

    MCP Server (stdio, JSON-RPC 2.0)
      ← 可接入 Claude Desktop / 其他 MCP 客户端
```

## 对话示例

```
用户: APP闪退怎么办？
Agent: [Thought: 检索历史方案]
       调用 search_solutions("APP闪退")
       → 找到 2 条相似工单
       → "历史案例：1. APP在iOS 18下闪退（高优先级，处理中）
          2. APP页面加载缓慢（已解决，CDN节点故障）

用户: 把第一个工单分配给张三
Agent: [Thought: 上一轮提到了 TK20240501002]
       调用 assign_ticket("TK20240501002", "张三")
       → 已分配

用户: 给它加一条回复：正在排查iOS兼容性
Agent: 调用 add_ticket_reply("TK20240501002", "正在排查iOS兼容性")
       → 回复已添加
```

## 项目结构

```
mcp-agent-tickets/
├── backend/
│   ├── config.py         # .env 配置管理
│   ├── logger.py         # 结构化日志
│   ├── database.py       # SQLite CRUD (2 表, 17 条种子数据)
│   ├── tools.py          # 7 个工具业务函数
│   ├── prompts.py        # ReAct 系统提示词
│   ├── agent.py          # llm.bind_tools() 手动循环 (7 工具)
│   ├── rag.py            # ChromaDB 向量检索 (DeepSeek Embedding)
│   └── mcp_server.py     # MCP stdio 服务器 (JSON-RPC 2.0)
├── frontend/
│   └── app.py            # Streamlit 聊天界面
├── docs/                 # PRD / Tech Design / AGENTS
├── .env.example
├── requirements.txt
├── Dockerfile
└── README.md
```

## 技术栈

| 层级 | 技术 |
|:---|:---|
| 前端 | Streamlit |
| Agent | LangChain + llm.bind_tools() |
| LLM | DeepSeek API (deepseek-v4-flash) |
| Embedding | DeepSeek API (text-embedding-3-small) |
| 向量库 | ChromaDB |
| 数据库 | SQLite |
| 协议 | MCP (JSON-RPC 2.0 over stdio) |
| 日志 | Python logging |
| 部署 | Docker (多阶段构建) |

## 许可证

MIT
