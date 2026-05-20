# LineMind

**LangGraph 驱动的工单智能助手** — Agent 闭环执行框架。

> 当前版本处于架构升级期。详见 [PLAN.md](PLAN.md)。

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
streamlit run frontend/app.py
```

浏览器打开 http://localhost:8501。

## 能力

| 能力 | 状态 |
|------|:---:|
| 工单查询/筛选/详情 | ✅ |
| 统计分析 + 图表（Plotly/Matplotlib） | ✅ |
| RAG 方案检索（双通道：向量 + FTS5） | ✅ |
| 工单操作（分配/更新/回复） | ✅ |
| SQL 查询 + Schema 探索 | ✅ |
| 智能推荐 + 日报 | ✅ |
| 安全熔断 + 重试 + 沙箱 | ✅ |
| 流式输出 | ✅ |
| Agent 多步执行闭环 | 🔨 开发中 |
| 评测（50 题） | ✅ |

## 技术栈

| 层级 | 技术 |
|:---|:---|
| Agent 框架 | LangGraph |
| LLM | DeepSeek（OpenAI 兼容） |
| 工具协议 | MCP（JSON-RPC 2.0 over stdio） |
| 向量检索 | ChromaDB + 阿里百炼 text-embedding-v3 |
| 前端 | Streamlit 流式输出 |
| 数据库 | SQLite（13 表星型 Schema） |
| 评测 | 50 题测试集 + 全客观指标 |

## 项目结构

```
linemind/
├── backend/
│   ├── agent_loop.py      ← Agent 核心循环（开发中）
│   ├── tools.py           ← 12 工具 + 断路器 + 沙箱
│   ├── rag.py             ← RAG 双通道检索
│   ├── graph.py           ← LangGraph 状态图
│   ├── database.py        ← SQLite + 种子数据
│   ├── config.py / logger.py / scheduler.py
│   └── mcp_server.py      ← MCP stdio 服务
├── frontend/
│   └── app.py             ← Streamlit UI
├── eval/
│   ├── judge.py           ← 评测脚本
│   └── test_queries.json  ← 50 题评测集
├── AGENTS.md              ← Claude 开发入口
├── PLAN.md                ← 完整优化计划
└── CHANGELOG.md           ← 版本记录
```

## License

MIT
