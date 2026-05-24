# AGENTS.md — LineMind

> Claude/OpenCode 会话入口。`/clear` 后读此文件恢复上下文。

## 启动

```powershell
cd "E:\develop\claude\项目开发2\LineMind\linemind"
streamlit run frontend/app.py   # → http://localhost:8501
```

## 项目定位

**闭环 Agent 执行框架**（制造业工单为验证场景）。核心是 Agent Loop + RAG 双通道 + 工具安全层。

## 当前状态

```
v5.1 — 全部 Phase 已完成 ✅
  ✓ Phase 1: 种子数据 / 知识库 / 2 新工具
  ✓ Phase 2: Context Engine — 三层组装 / 回合压缩
  ✓ Phase 3: Agent 稳定性 — TOOL_CALL_LIMITS / 动态移除 / 每轮上限
  ✓ Phase 4: 评测重写 — 54 题 + required/optional 双列表
  ✓ Agentic Tracing — 自动记录 trace 到 SQLite
  ✓ Go API — GO_API_KEY 优先 + Direct 备用 + 耗尽自动切
  ✓ RAG — 双通道向量+关键词 + RRF 融合
```

## 架构

```
AgentLoop.run() — while(hasToolCalls) 循环
  ├── Plan → Act(LLM + Tools) → Observe(代码检查) → Reflect
  ├── Context Engine: _assemble_context (三层) + _compact_tool_results
  ├── Stability: TOOL_CALL_LIMITS 分级限频 + _should_stop 退出判断
  ├── graph.py: 薄壳（LLM 创建 + 工具执行 + 流式转发）
  └── 14 工具

不变模块: tools.py / rag.py / database.py / knowledge_base.py / scheduler.py
```

## 关键文件

| 文件 | 职责 | 状态 |
|------|------|:---:|
| `backend/agent_loop.py` | Agent 核心循环 + Context Engine + 限频 + 循环检测 + Trace | ✅ |
| `backend/graph.py` | LLM 双通道(Go/Direct) + 工具注册 + 流式转发 | ✅ |
| `backend/prompts.py` | AGENT_PROMPT(7 铁则) + FINAL_ANSWER_PROMPT | ✅ |
| `backend/tools.py` | 14 工具函数 | 稳定 |
| `backend/rag.py` | 向量 + FTS5 双通道检索 + RRF 融合 | ✅ |
| `backend/database.py` | SQLite 15 表(含 traces) + 种子数据 | ✅ |
| `backend/trace_viewer.py` | CLI 查看/统计 trace 数据 | 新 |
| `frontend/app.py` | Streamlit UI (深色主题) | 稳定 |
| `eval/test_queries.json` | 54 题评测集（4 类 4 难度） | ✅ |
| `eval/judge.py` | 评测框架（覆盖率+完成度+步数分布） | ✅ |

## 评测

```powershell
# 全量回归（~12 分钟）
python eval/judge.py -n 54 -o eval/report.json

# 跑前 10 题快速验证
python eval/judge.py -n 10

# 查看 Trace
python backend/trace_viewer.py              # 最近 20 条列表
python backend/trace_viewer.py <trace_id>   # 单条详情
python backend/trace_viewer.py --stats 54   # 统计聚合
```

**最近一次回归结果 (v5.1):**

| 指标 | 结果 |
|------|------|
| 必要工具覆盖率 | 48/54 (88.9%) |
| 任务完成度 | 0.89 |
| 工具执行成功率 | 160/160 (100%) |
| 崩溃率 | 0/54 (0%) |
| 平均延迟 | 13.9s/题 |

## 开发流程

1. 改代码 → 重启 Streamlit → 浏览器测
2. `python eval/judge.py -n 10` 快速回归
3. 每步改完 → `git add` + `git commit`
4. Phase 完成 → 全量回归 + 更新本文

## 已知问题

- Streamlit 流式输出后页面自动滚底（Streamlit 内在限制，非功能问题）
- 多步查询中 Agent 偶尔用 SQL/Python 绕路（已有 TOOL_CALL_LIMITS 兜底）

## 环境变量

```
DEEPSEEK_API_KEY=sk-xxx
GO_API_KEY=sk-xxx           # OpenCode Go API (可选)
BAIDU_API_KEY=bce-v3/ALTAK-xxx
EMBEDDING_API_KEY=sk-xxx    # DashScope Embedding
```

## Git

```
仓库: E:\develop\claude\项目开发2\LineMind\linemind
分支: master
远端: origin/master
```
