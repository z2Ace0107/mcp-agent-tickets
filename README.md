# 🎫 MCP 智能工单 Agent 系统

基于 **MCP 协议** 的标准化 AI Agent 系统，演示如何通过 `llm.bind_tools()` 调用企业工单工具，完成智能查询与统计分析。项目对标企业 AI Agent 开发岗位。

> **当前版本：v1.0.0 MVP**

## 功能

| 功能 | 说明 |
|:---|:---|
| 🔍 工单查询 | 自然语言输入 → Agent 自动调用 `query_tickets` 工具 |
| 📊 工单分析 | 类型分布 / 状态统计 / 优先级分布 / 每日趋势 |
| 🧠 ReAct 推理 | 侧边栏实时展示 Thought → Action → Observation |
| 💬 多轮对话 | Streamlit 聊天界面，支持上下文连续提问 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置 API Key

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "your-api-key"

# macOS / Linux
export DEEPSEEK_API_KEY="your-api-key"
```

### 3. 启动

```bash
# 前端聊天界面（推荐）
streamlit run frontend/app.py

# MCP 工具服务器
python -m backend.mcp_server
```

启动后在浏览器打开 http://localhost:8501，侧边栏输入 API Key 即可开始对话。

### Docker 启动

```bash
docker build -t mcp-agent-tickets .
docker run -p 8501:8501 -e DEEPSEEK_API_KEY="your-key" mcp-agent-tickets
```

## 架构

```
用户输入 (Streamlit)
    │
    ▼
Agent 核心 (llm.bind_tools + 手动循环)
    │
    ├── query_tickets ──→ 模拟工单数据 (17 条)
    │
    └── analyze_tickets ──→ 统计分析
    │
    ▼
ReAct 推理可视化 (侧边栏 Thought / Action / Observation)
```

## 项目结构

```
mcp-agent-tickets/
├── backend/
│   ├── tools.py         # 工具定义 + 17 条模拟工单
│   ├── prompts.py       # ReAct 系统提示词
│   ├── agent.py         # llm.bind_tools() 手动工具调用循环
│   └── mcp_server.py    # FastAPI MCP 工具服务器
├── frontend/
│   └── app.py           # Streamlit 聊天界面
├── docs/                # 设计文档 (PRD / Tech Design / AGENTS)
├── requirements.txt
├── Dockerfile
└── README.md
```

## 对话示例

```
用户：最近一周有哪些退款工单？
Agent：调用 query_tickets(ticket_type="退款", date_range="week")
       → 返回 3 条工单，列出标题和状态

用户：帮我分析一下工单的状态分布
Agent：调用 analyze_tickets(analysis_type="status_distribution")
       → 待处理 6 条 (35.3%) / 处理中 5 条 (29.4%) / ...

用户：你好
Agent：不调用任何工具，直接回复问候语
```

## 技术栈

| 层级 | 技术 |
|:---|:---|
| 前端 | Streamlit |
| Agent | LangChain + llm.bind_tools() |
| LLM | DeepSeek API (deepseek-v4-flash) |
| 工具服务 | FastAPI + MCP 协议 |
| 部署 | Docker |

## 许可证

MIT