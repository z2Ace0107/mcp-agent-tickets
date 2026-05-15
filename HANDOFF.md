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

## 当前状态：v3.2 稳定 ✅

```
v2.0 ✅ → v3.1 ✅ → v3.2 ✅ → v3.3 待重做 → v3.4 → v4.0
```

### v3.2 已完成功能

| 文件 | 功能 |
|------|------|
| `backend/scheduler.py` | 告警检测（3条规则）+ 日报生成 + 告警缓存 |
| `frontend/app.py` | 侧边栏工具箱（快捷查工单/提醒/一键日报/演示/上下文状态） |
| | 5 个快速操作按钮（今日概览/智能推荐/紧急工单/设备故障/统计报告） |
| | 实时监控 toggle（60s 自动刷新） |

### 验证方式

```powershell
python test_agent.py                    # CLI 测试（LLM 或 DB 回退）
streamlit run frontend/app.py           # UI 黄金路径
```

---

## v3.3 重做计划

### 第一轮失败教训（2026-05-15）

| # | 问题 | 教训 |
|---|------|------|
| 1 | agent_node 工具列表只有 6 个，缺 recommend_tickets/execute_python | **所有 12 个工具都必须注册到 agent_node 的 function calling 列表** |
| 2 | 种子数据日期全是 4月28日-5月8日，"今天"查询永远为空 | **种子数据必须包含当天日期的工单（动态 datetime.now()）** |
| 3 | 数据库重置只删了 4 张 v2 表，v3.3 新增的 4 张表未清 → UNIQUE 冲突 | **新增表时必须同步更新重置逻辑** |
| 4 | 种子 INSERT 用硬 INSERT，重置时重复插入崩溃 | **种子数据全部用 INSERT OR IGNORE** |
| 5 | langgraph 装到了系统 Python 而非 .venv | **先确认 venv 路径再 pip install** |
| 6 | 中文全角引号 `""` 在 Python 字符串中导致语法错误 | **Python 字符串内中文引号用「」或 [] 替代** |
| 7 | 工具描述里写错了 SQL 示例导致 Agent 生成错误 SQL | **工具 description 里的示例必须经过实测** |

### v3.3 目标（不变）

```
5 表星型 Schema + LangGraph 4 节点 + Self-Correction + MCP 同步
```

### 实施顺序（严格按序，每步验证）

1. **环境准备** — `pip install langgraph` 到 .venv，确认导入无报错
2. **数据层** — database.py 新增 4 表 + 种子数据，INSERT OR IGNORE，含当天日期工单
3. **工具层** — tools.py 新增 get_schema / execute_sql / execute_python
4. **MCP 同步** — mcp_server.py 注册 3 个新工具
5. **LangGraph** — 新建 graph.py，12 工具全部注册
6. **桥接** — agent.py run_agent() 改为调用 LangGraph，保留 _run_agent_legacy() 回退
7. **前端联动** — 重置按钮覆盖全部 8 张表
8. **全链路测试** — 7 条标准对话用例全部通过

---

## 可优化项（来自本轮对话）

### Bug 修复（v3.2 已稳定，以下为记录）

| # | 问题 | 修复方案 |
|---|------|----------|
| 1 | 告警 detail 只展示前 5 条，count > 5 时无省略标记 | 追加 `...等共{count}条` |
| 2 | priority_distribution 遗漏"紧急"类别 | order 列表加 "紧急" |
| 3 | generate_report_text() 概览依赖 stats 参数 key | 改为从 DB 查询取值 |

### UI 优化（下版本实现）

| # | 优化点 | 方案 |
|---|--------|------|
| 1 | 快速操作按钮在页面顶部，对话深了要翻页 | 侧边栏加快捷操作下拉框（或吸顶 CSS） |
| 2 | 实时监控 toggle 无视觉反馈 | 绿点脉动动画 + "监控运行中" 标签 + 告警计数 |
| 3 | 演示场景和快捷操作 80% 重叠 | 合并为一个下拉，命名为"快捷操作" |
| 4 | 工具箱"提醒"无手动刷新入口 | 加"🔄 刷新告警"按钮 |

---

## 项目结构（v3.2）

```
mcp-agent-tickets/
├── frontend/app.py          — Streamlit 前端（v3.0 UI + 工具箱 + 实时监控）
├── backend/
│   ├── __init__.py          — init_app() 入口
│   ├── config.py            — Settings（pydantic-settings）
│   ├── logger.py            — 日志
│   ├── database.py          — SQLite（4 表 + 20 条种子工单 + 对话 CRUD）
│   ├── tools.py             — 9 个工具函数
│   ├── prompts.py           — 全部 Prompt
│   ├── agent.py             — LangChain Agent v3.0（预处理/安全/预算/记忆）
│   ├── scheduler.py         — v3.2 告警检测 + 日报生成
│   ├── rag.py               — ChromaDB 向量检索
│   └── mcp_server.py        — MCP stdio 服务器（9 工具）
├── .env                     — API Key（不提交）
├── .env.example             — 配置模板
├── requirements.txt         — Python 依赖
├── test_agent.py            — CLI 测试
├── CHANGELOG.md             — 版本记录
└── README.md                — 项目说明
```

## 技术栈

Python 3.10+ / LangChain / DeepSeek v4-flash / Streamlit / ChromaDB / SQLite / MCP (JSON-RPC stdio)

## 文档维护规则

- **AGENTS.md**: 加新功能/改架构时更新（不记 bug 修复）
- **CHANGELOG.md**: 每个版本提测通过后追加（新增/增强/修复 三块）
- **HANDOFF.md**: `/clear` 恢复上下文用，随时保持与当前代码一致
