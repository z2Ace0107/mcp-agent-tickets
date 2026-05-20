# AGENTS.md — LineMind

> Claude 会话入口。`/clear` 后读此文件恢复上下文。拿项目给别人看也先读这个。

## 启动

```powershell
cd "E:\develop\claude\项目开发2\LineMind\linemind"
.venv/Scripts/Activate.ps1
streamlit run frontend/app.py   # → http://localhost:8501
```

## 项目定位

**闭环 Agent 执行框架**（工单是验证场景，不是全部）。核心是 Agent Loop + RAG 双通道 + 工具安全层。

## 当前状态

```
v5.0 进行中

已完成:
  ✓ 死代码清理（200行旧 prompt / agent_actions表 / sql_templates表 / correction_rules表）
  ✓ Reporter 节点移除（Agent 最终回复直接输出）
  ✓ 对话记忆 + Supervisor 上下文短追问
  ✓ 评测重构（全客观指标，零 LLM 消耗）
  ✓ 文档整合（HANDOFF → AGENTS，7→4 文档）
  ✓ PLAN.md v2 重写（基于 zero2Agent 理论框架）

待做:
  □ agent_loop.py — Agent 核心循环（项目灵魂）
  □ graph.py 简化 — 5 节点 → 2 节点
  □ prompts.py 重写 — 4 角色 Prompt → 1 个 Agent Prompt
  □ 前端适配新 Agent Event 流
  □ 评测集重写（真正多步题）
  □ 跑评测验证 + RAG 回归
```

## 架构

### 当前（v4.x / v5.0 过渡期）

```
Supervisor → Query Agent (6工具) / Analyze Agent (3工具) / Knowledge Agent (3工具)
              ↓ 每个 Agent 调一次工具就停
           Tool Executor (断路器/重试/超时/沙箱)
```

**已知问题：** 4-Agent 本质是同一个模型绑了 3 组不同 prompt，共享一个执行循环。每次只调一次工具就结束，没有真正的多步执行。见 [PLAN.md](PLAN.md) 完整诊断。

### 目标（改造后）

```
Agent (agent_loop.py) → Tool Executor → Agent → ... → END
    ↑                       │
    └───────────────────────┘
       while(hasToolCalls) 循环
       Plan → Act → Observe → Reflect
```

LangGraph 退化为 2 节点薄壳（状态管理 + 流式输出）。

## 开发流程

1. 改代码 → 重启 Streamlit → 浏览器测
2. `python eval/judge.py -n 10 --seed 42` 快速评测
3. `python eval/bench_rag.py` RAG 回归
4. 每步改完 → `git add` + `git commit` → 给你检查

## 关键文件

| 文件 | 职责 | 状态 |
|------|------|:---:|
| `backend/agent_loop.py` | Agent 核心循环 | **待建** |
| `backend/tools.py` | 12 工具 + 断路器 + 沙箱 | 稳定 |
| `backend/rag.py` | RAG 双通道检索 | 稳定 |
| `backend/graph.py` | LangGraph 图（当前 5 节点 → 目标 2 节点） | 待改 |
| `backend/prompts.py` | Agent Prompt（当前 4 角色 → 目标 1 个） | 待改 |
| `backend/nodes/` | Supervisor + 3 子 Agent 节点 | **待删** |
| `frontend/app.py` | Streamlit 流式 UI | 待小改 |
| `eval/judge.py` | 评测脚本 | 待适配 |
| `eval/test_queries.json` | 50 题评测集 | 待重写 |

## 文档索引

| 文档 | 内容 |
|------|------|
| [PLAN.md](PLAN.md) | 完整项目优化计划（Agent Loop 设计 + 实施步骤 + 评测方案） |
| [CHANGELOG.md](CHANGELOG.md) | 版本记录 |
| [README.md](README.md) | 基础介绍（Agent Loop 完成后重写） |

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

### 最近提交（v5.0 过渡期）

```
695a974 docs: PLAN.md v2 — Agent Loop 核心优化计划
00b7b19 docs: 文档整合 — 7→4，PLAN.md 为完整项目计划
3d7ac7b fix: 对话记忆 + Supervisor 上下文短追问
86bc728 v5.0 移除 Reporter 节点: Agent 最终回复直接输出
22335b0 fix: 双重防御 — extract_final_output 跳过假 tool_calls
7c69ff2 fix: 所有 Agent 节点始终注入 system prompt
9aedc44 fix: Reporter 始终注入 system prompt
c8da154 fix: Reporter 用 tool_choice="none" 阻止 LLM 模仿历史 tool_calls
1fe48a5 v5.0 删死代码: config MCP_SERVER_PORT + frontend 旧标签 + eval 旧报告
b0ca677 v5.0 删死表: database.py 移除 agent_actions/sql_templates/correction_rules
141d93c v5.0 删死代码: prompts.py 移除 v2.0 遗留 (~200行)
ed9959d v5.0 评测重构: 全客观指标，零 LLM 消耗
```
