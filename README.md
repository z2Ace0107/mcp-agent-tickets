# LineMind

**闭环 Agent 执行框架** — 以制造业工单为验证场景，展示 Agent 开发全链路。

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## 核心能力

| 能力 | 说明 |
|------|------|
| Agent 闭环执行 | ReAct 循环 (Plan→Act→Observe→Reflect)，while(hasToolCalls) 自动推进 |
| 14 个工具 | 工单查询/分析/分配/更新 + SQL/Python 执行 + 知识检索 + 联网搜索 |
| Context Engine | 三层消息组装 + 轮次边界压缩 + 回合内工具结果压缩 |
| 工具限频分级 | TOOL_CALL_LIMITS 按工具语义分级，达上限后从 LLM 视野中移除 |
| Agentic Tracing | 每次执行自动记录 trace，CLI 查看/统计/详情 |
| RAG 双通道检索 | ChromaDB 向量 + FTS5 关键词 → RRF 融合排序 |
| 评测体系 | 54 题 (4 类 4 难度)，必要工具覆盖率 + 任务完成度 + 步数分布 |
| LLM 双通道降级 | Go API 优先 → Direct 直连 DeepSeek 备用，额度耗尽自动切换 |

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
streamlit run frontend/app.py
```

浏览器打开 http://localhost:8501。

## 评测

```bash
# 全量回归（54 题，约 12 分钟）
python eval/judge.py -n 54 -o eval/report.json

# 快速验证（前 10 题）
python eval/judge.py -n 10
```

**最新结果 (v5.1):**

| 指标 | 结果 |
|------|------|
| 必要工具覆盖率 | 48/54 (88.9%) |
| 任务完成度 | 0.89 |
| 工具执行成功率 | 160/160 (100%) |
| 崩溃率 | 0/54 (0%) |
| 平均延迟 | 13.9s/题 |

## Trace 查看

```bash
python backend/trace_viewer.py              # 最近 20 条列表
python backend/trace_viewer.py <trace_id>   # 单条详情
python backend/trace_viewer.py --stats 54   # 统计聚合
```

## 架构

```
AgentLoop.run() — while(hasToolCalls) 循环
  ├── Act:    LLM 决策 + bind_tools 调用工具
  ├── Observe: 程序化检查 (error/empty/duplicate/ok)
  ├── Reflect: 观察注入 prompt, 更新状态
  ├── Compact: Context Engine 上下文压缩
  ├── ShouldStop? → 生成最终答案 : 继续循环
  └── Trace:   自动记录执行轨迹到 SQLite
```

## 技术栈

| 层级 | 技术 |
|:---|:---|
| Agent 框架 | LangChain (bind_tools + ainvoke) |
| LLM | DeepSeek / OpenCode Go API |
| 工具 | 14 个 LangChain @tool + 断路器 + 指数退避重试 |
| 向量检索 | ChromaDB + DashScope text-embedding-v3 |
| 关键词检索 | SQLite FTS5 |
| 数据库 | SQLite 15 表 (星型 Schema) |
| 前端 | Streamlit |
| 评测 | judge.py (全客观指标) |

## 项目结构

```
linemind/
├── backend/
│   ├── agent_loop.py      ← Agent 核心循环 + Context Engine + Trace
│   ├── graph.py           ← LLM 创建 + 工具注册 + 流式转发
│   ├── tools.py           ← 14 工具函数
│   ├── rag.py             ← 双通道 RRF 检索
│   ├── database.py        ← SQLite + 种子数据 + trace CRUD
│   ├── prompts.py         ← AGENT_PROMPT (7 铁则) + FINAL_ANSWER_PROMPT
│   ├── knowledge_base.py  ← 设备手册 + SOP + 巡检记录
│   ├── trace_viewer.py    ← CLI trace 查看/统计
│   ├── config.py / logger.py / scheduler.py
│   └── mcp_server.py      ← MCP stdio 服务
├── frontend/
│   └── app.py             ← Streamlit UI
├── eval/
│   ├── judge.py           ← 评测框架
│   ├── test_queries.json  ← 54 题评测集
│   └── bench_rag.py       ← RAG 消融实验
├── AGENTS.md              ← Claude/OpenCode 开发入口
├── CHANGELOG.md           ← 版本记录
├── PLAN_v5.2.md           ← v5.2 优化计划
└── README.md
```

## License

MIT
