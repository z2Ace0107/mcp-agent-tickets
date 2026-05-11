# 交接文档 — MCP 智能工单 Agent 系统 v2.0

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
├── requirements.txt          — 依赖（含 ddgs 联网搜索）
├── test_agent.py             — 测试脚本（LLM 测试 + 数据库回退测试）
├── frontend/
│   └── app.py                — 主前端（深色主题，无主题切换）
├── backend/
│   ├── __init__.py           — init_app() 入口（含 RAG 索引构建）
│   ├── config.py             — Settings 类
│   ├── logger.py             — 日志
│   ├── database.py           — SQLite（工单 CRUD + 对话 CRUD + 分组查询 + 置顶）
│   ├── tools.py              — 9 个工具函数（含智能推荐 + 联网搜索）
│   ├── prompts.py            — ReAct 系统提示词（含多工具编排规则）
│   ├── agent.py              — LangChain Agent（llm.bind_tools 手动循环，9 工具）
│   ├── mcp_server.py         — MCP stdio 服务器（9 个工具定义）
│   └── rag.py                — ChromaDB 向量检索
├── data/                     — tickets.db（运行时生成）
├── chroma_data/              — ChromaDB 持久化
└── logs/                     — 日志文件
```

## 已完成的全部功能

### 基础架构
| 功能 | 状态 |
|------|------|
| 深色主题（base="dark"，无切换） | ✅ |
| 统计卡片（4 个渐变卡片：总数/待处理/处理中/紧急） | ✅ |
| ReAct 推理折叠 + 工具名中文映射（TOOL_CN_MAP） | ✅ |
| API Key 无感：.env 有则隐藏输入框，顶部连接状态灯 | ✅ |
| 对话历史 SQLite 持久化 + 侧边栏管理 | ✅ |
| 一键备注到工单（📝 → 弹窗 → add_ticket_reply） | ✅ |
| 快捷操作按钮行（5 个：今日概览/智能推荐/紧急工单/设备故障/统计报告） | ✅ |
| 演示模式（侧边栏下拉 + 快捷操作，6 个场景） | ✅ |
| 复制 + 导出 Markdown + 下载 | ✅ |
| 重置工单数据 | ✅ |

### Agent 工具（9 个）
| # | 工具 | 用途 |
|---|------|------|
| 1 | query_tickets | 按条件筛选工单 |
| 2 | analyze_tickets | 统计分析（分布/趋势/汇总） |
| 3 | update_ticket_status | 更新工单状态 |
| 4 | assign_ticket | 分配处理人 |
| 5 | add_ticket_reply | 添加回复 |
| 6 | get_ticket_detail | 获取工单详情 |
| 7 | search_solutions | RAG 检索历史方案（ChromaDB） |
| 8 | recommend_tickets | **智能推荐**（紧急识别+分配建议+关联发现） |
| 9 | web_search | **联网搜索**（DuckDuckGo 实时搜索） |

### 真实工厂工单数据（20 条）
| 类型 | 数量 | 示例 |
|------|------|------|
| 设备故障 | 5 | CNC主轴异响、注塑温控失控、空压机跳闸、AGV撞架、焊接偏移 |
| 质量异常 | 4 | 钢材硬度不合格、密封圈装反、盐雾锈点、喷漆颗粒退货 |
| 安全隐患 | 3 | 安全光幕短接、化学品泄漏、叉车氢气积聚 |
| 物料短缺 | 2 | 进口轴承延误、304不锈钢盘点差异 |
| 工艺问题 | 2 | 淬火变形超标、SMT回流焊漂移 |
| 生产计划 | 2 | 紧急插单排产、保养交付冲突 |
| 环境监测 | 2 | VOCs排放超标、冷却水藻类 |

每条工单含：设备编号/型号、技术参数、影响评估、根因分析、处置措施。

### 对话历史（DeepSeek 风格）
| 功能 | 说明 |
|------|------|
| 时间分组 | 置顶 / 今天 / 昨天 / 7天内 / 更早 |
| 置顶 | 重要对话固定顶部 |
| ⋯ 菜单 | 重命名 / AI生成短标题 / 置顶(取消) / 删除 |
| 标题截断 | 超过20字自动截断 + tooltip 显示完整标题 |
| 当前对话 | 蓝色 primary 按钮高亮 |

## 当前已知问题

1. **⋯ 按钮 hover 效果不完善**：CSS `conv-menu-btn` 包裹了 popover 但 Streamlit 渲染的 DOM 结构导致 CSS 选择器不一定能匹配到按钮。需要验证实际 DOM 结构调整 CSS。

## 关键设计决策

- **Agent 模式**: LangChain `llm.bind_tools()` 手动循环（最多 5 轮），不用 `AgentExecutor`
- **LLM**: DeepSeek v4-flash，通过 OpenAI 兼容 API，关掉 thinking
- **Embedding**: 阿里云百炼 `text-embedding-v3`
- **主题**: Streamlit 原生深色（base="dark"），不再做 CSS 覆盖切换
- **多工具编排**: prompts.py 中有规则指导 Agent 在同一轮中链式调用多个工具
- **联网搜索**: DeepSeek API 不支持，改用 DuckDuckGo（ddgs 包）
- **对话持久化**: 每条消息即时写入 SQLite，新对话自动创建

## 数据库 Schema

```sql
tickets (id, ticket_id, title, type, status, priority, assignee, created_at, updated_at, description)
  — 20 条工厂种子工单，日期 2026-04-10 ~ 2026-05-08

ticket_replies (id, ticket_id, content, created_at)

conversations (id, title, created_at, updated_at, pinned)
  — pinned: 0/1 置顶标记

conversation_messages (id, conversation_id, role, content, steps, created_at)
```

## 测试命令

```powershell
# 命令行测试
python test_agent.py

# UI 测试
streamlit run frontend/app.py

# MCP Server 测试
python backend/mcp_server.py
```
