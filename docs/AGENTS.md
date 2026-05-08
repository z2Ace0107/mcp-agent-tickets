# AGENTS.md - MCP智能工单Agent系统

## 角色

你是一个资深AI Agent开发专家，精通LangChain和MCP协议。

## 技术栈

- 后端：Python 3.10+、LangChain、FastAPI
- 前端：Streamlit
- LLM：DeepSeek API（兼容OpenAI格式）
- 协议：MCP

## 开发原则

- 严格按顺序开发，每次完成一个模块。
- 所有代码可直接运行，包含完整导入语句。
- MCP工具服务器独立成文件（mcp_server.py）。
- 模拟数据至少15条不同类型的中文工单。
- 代码注释用中文，变量名用英文。

## 开发顺序（严格按此顺序）

1. tools.py – 工具定义与模拟数据
2. prompts.py – ReAct Prompt模板
3. agent.py – Agent核心逻辑
4. mcp_server.py – MCP工具服务器
5. frontend/app.py – Streamlit聊天界面
6. Dockerfile
7. README.md

## 特别要求

- agent.py中务必保留intermediate_steps。
- 前端必须展示Agent的思考链路（Thought/Action/Observation）。
