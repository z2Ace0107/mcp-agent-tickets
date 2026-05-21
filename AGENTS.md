# AGENTS.md — LineMind

> Claude 会话入口。`/clear` 后读此文件恢复上下文。

## 启动

```powershell
cd "E:\develop\claude\项目开发2\LineMind\linemind"
.venv/Scripts/Activate.ps1
streamlit run frontend/app.py   # → http://localhost:8501
```

## 项目定位

**闭环 Agent 执行框架**（制造业工单为验证场景）。核心是 Agent Loop + RAG 双通道 + 工具安全层。

## 当前状态

```
v5.1 进行中 — Phase 1: 数据 & 环境扩展

v5.0 已完成:
  ✓ agent_loop.py — Agent 核心循环（Plan → Act → Observe → Reflect）
  ✓ prompts.py 重写 — 4 角色 Prompt → 1 个 AGENT_PROMPT
  ✓ graph.py 简化 — 5 节点 → AgentLoop 驱动
  ✓ 旧节点删除 — nodes/ 全目录 + 旧 agent.py
  ✓ 前端适配 — 移除路由徽标、意图识别、死字段
  ✓ 上下文污染修复 — HumanMessage(goal) 放在最后
  ✓ 程序化守卫 — search_solutions/web_search 各只一次

v5.1 待做:
  □ Phase 1: 数据扩展 (33→80+ 工单, 知识库, 2 新工具)
  □ Phase 2: Context Engine (消息分层 + 轮次压缩)
  □ Phase 3: Agent 稳定性 (工具限频分级 + Turn State)
  □ Phase 4: 评测重写 (50 题)
  □ Phase 5: 前端优化 (回答消失 + ReAct 美化)
  □ Phase 6: 文档 + 全量回归
```

## 架构

```
AgentLoop.run() — while(hasToolCalls) 循环
  ├── Plan → Act(LLM + Tools) → Observe(代码检查) → Reflect
  ├── graph.py: 薄壳（LLM 创建 + 工具执行 + 流式转发）
  └── 14 工具: 12 原有 + 2 新增 (search_manual, query_inspection)

不变模块: tools.py / rag.py / database.py / mcp_server.py / scheduler.py
```

## 开发流程

1. 改代码 → 重启 Streamlit → 浏览器测
2. `python test_agent_loop.py` 核心测试
3. `python eval/bench_rag.py` RAG 回归
4. 每步改完 → `git add` + `git commit` → 给你检查
5. 每 Phase 完成后更新 CHANGELOG.md

## 关键文件

| 文件 | 职责 | 状态 |
|------|------|:---:|
| `backend/agent_loop.py` | Agent 核心循环 + Context Engine | **待优化** |
| `backend/tools.py` | 14 工具（12 原有 + 2 新增） | **待扩展** |
| `backend/knowledge_base.py` | 设备手册 + SOP + 巡检 | **待建** |
| `backend/rag.py` | RAG 双通道检索 | 稳定 |
| `backend/database.py` | SQLite 13 表 + 种子数据 | **待扩展** |
| `backend/graph.py` | LLM + 工具注册 + 流式转发 | 稳定 |
| `backend/prompts.py` | AGENT_PROMPT + FINAL_ANSWER_PROMPT | 稳定 |
| `frontend/app.py` | Streamlit UI | **待优化** |
| `eval/test_queries.json` | 50 题评测集 | **待重写** |
| `eval/judge.py` | 评测框架 | **待适配** |

## 文档索引

| 文档 | 内容 |
|------|------|
| [PLAN.md](PLAN.md) | 项目优化计划（v5.0 + v5.1） |
| [CHANGELOG.md](CHANGELOG.md) | 版本记录 |
| [README.md](README.md) | 基础介绍（v5.1 完成后重写） |

## 环境变量

```
DEEPSEEK_API_KEY=sk-xxx
BAIDU_API_KEY=bce-v3/ALTAK-xxx
EMBEDDING_API_KEY=sk-xxx
```

## Git

```
仓库: E:\develop\claude\项目开发2\LineMind\linemind
分支: master
远端: origin/master
```
