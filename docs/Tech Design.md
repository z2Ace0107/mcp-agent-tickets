# Tech Design: MCP智能工单Agent系统

## 系统架构

Streamlit前端 → LangChain Agent (ReAct) → MCP工具服务器 → 模拟数据

## 技术栈

- Python 3.10+
- LangChain
- FastAPI
- DeepSeek API
- Streamlit
- Docker

## 目录结构

mcp-agent-tickets/
├── frontend/
│   └── app.py
├── backend/
│   ├── tools.py
│   ├── prompts.py
│   ├── agent.py
│   └── mcp_server.py
├── requirements.txt
├── Dockerfile
└── README.md

## MCP工具设计

| 工具            | 描述     | 参数                            | 返回           |
| :-------------- | :------- | :------------------------------ | :------------- |
| query_tickets   | 查询工单 | ticket_type, status, date_range | 工单列表(JSON) |
| analyze_tickets | 分析工单 | analysis_type                   | 统计结果(JSON) |

模拟数据需包含15条以上不同类型的中文工单。

## Agent设计

- 模式：ReAct
- 温度：0
- 错误处理：解析错误时自动重试（最多3次）

## 前端设计

- 聊天主窗口：对话历史。
- 侧边栏：折叠显示Thought/Action/Observation。
