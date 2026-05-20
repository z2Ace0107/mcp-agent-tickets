# AgentForge — 完整优化计划 v2

> 目标：把 Agent 层从"多角色 Prompt"升级为真正的闭环 Agent 系统

---

## 一、现状诊断

### 1.1 分层成熟度

| 层 | 评分 | 现状 |
|----|:---:|------|
| **Agent** | ⭐ | 最弱。4-Agent Supervisor 本质是"同一个模型 + 同一个执行循环 + 换了 4 个 system prompt 名字"。每次只调一个工具就停，没有执行闭环 |
| Tools | ⭐⭐⭐⭐ | 12 工具 + 断路器 + 重试 + 超时 + Python 沙箱 + AST 分离 + Plotly 双引擎 |
| RAG | ⭐⭐⭐⭐ | 双通道（ChromaDB 向量 + FTS5 关键词 → RRF 融合）+ 15 题消融实验 |
| Eval | ⭐⭐⭐ | 50 题覆盖 6 类，全客观指标。但 40/50 题期望单工具调用，不测多步执行 |
| Data | ⭐⭐⭐ | 13 表星型 Schema，30+ 条真实工厂种子数据，含 FK 关联 |
| Config | ⭐⭐⭐ | .env.example 完备，启动验证 |
| Frontend | ⭐⭐ | 1247 行单文件，流式输出可用但 CSS/JS 嵌入 Python |

### 1.2 核心问题

当前 4-Agent 架构（Supervisor → Query/Analyze/Knowledge → Reporter）本质是 **Workflow 披着多 Agent 的皮**。

诊断依据（zero2Agent Basic 08）：
> "同一个模型、同一个上下文、同一个执行循环，只是换了几个 system prompt 名字——这更像是多角色提示词，不一定真的构成有意义的多 Agent 系统。"

三个子 Agent（query_node / analyze_node / knowledge_node）共享同一个 `_create_llm()`、同一套消息处理、同一个 AgentState。唯一区别是绑了不同的工具子集和换了 prompt。这不是多 Agent——**这是 3 张角色卡片**。

Agent 和 Chatbot 的本质区别（zero2Agent Basic 01 + Claude Code 01）：
> "Agent 是一个围绕目标持续推进任务的系统。while(hasToolCalls) 循环——检测到工具调用时继续执行并回调 LLM，而不是直接结束。"

当前系统没有这个循环。每个 Agent 调一个工具就停。

### 1.3 评测不匹配

50 道评测题中 40 道 `expected_tools` 只有 1 个工具。Q043 的 `check` 说"查询→搜索→汇总，跨 Agent 协作"，但 `expected_tools` 只列了 `query_tickets_tool`。**评测被旧架构的能力上限框住了。**

---

## 二、目标架构

### 2.1 核心改动

```
旧: Supervisor → Query/Analyze/Knowledge → 调一次工具 → END
新: Agent (agent_loop.py) → Tool Executor → Agent → ... → END
         ↑                          │
         └──────────────────────────┘
            while(hasToolCalls) 循环
```

**Agent Loop 是新的心脏**，LangGraph 退化为薄壳（状态管理 + 流式输出）。

### 2.2 架构分层

```
┌─ LangGraph（壳）─────────────────────────┐
│  agent_node ──→ tool_executor_node ──→ END│
│      ↑              │                     │
│      └──────────────┘                     │
│                                            │
│  agent_node 内部 = AgentLoop.run()          │
│    Plan → Act(LLM) → Observe(代码) → Reflect │
└────────────────────────────────────────────┘
```

### 2.3 文件结构（改造后）

```
linemind/
├── backend/
│   ├── agent_loop.py      ← ★ 新增：Agent 核心循环
│   ├── tools.py           ← 保留（12工具 + 断路器 + 沙箱）
│   ├── rag.py             ← 保留（双通道 RRF）
│   ├── database.py        ← 保留
│   ├── graph.py           ← 简化：2节点（agent + tool_executor）
│   ├── prompts.py         ← 重写：1个 AGENT_PROMPT
│   ├── config.py          ← 保留
│   ├── logger.py          ← 保留
│   ├── scheduler.py       ← 保留
│   └── mcp_server.py      ← 保留
├── frontend/
│   └── app.py             ← 小改（适配新 Event 流）
├── eval/
│   ├── judge.py           ← 评测框架保留
│   ├── bench_rag.py       ← 保留
│   └── test_queries.json  ← 重写（真正多步题）
├── CHANGELOG.md           ← 保留（记录小步更新）
├── AGENTS.md              ← Claude 开发入口 + 项目交接
├── PLAN.md                ← 本文档
└── README.md              ← 实现完成后重写
```

### 2.4 删除清单

```
backend/nodes/supervisor.py   # 意图分类由 Agent 自己完成
backend/nodes/query.py        # 合并为 agent_loop.py
backend/nodes/analyze.py      # 合并为 agent_loop.py
backend/nodes/knowledge.py    # 合并为 agent_loop.py
backend/nodes/__init__.py     # 目录清空
backend/agent.py              # 入口逻辑合并进 agent_loop.py
```

---

## 三、Agent Loop 设计

### 3.1 核心循环

```python
class AgentLoop:
    """围绕目标持续推进任务的执行循环。"""

    def __init__(self, llm, tools, max_iterations=8):
        self.llm = llm
        self.tools = tools          # 12 工具全集
        self.max_iterations = max_iterations

    async def run(self, goal: str, history: list) -> AsyncGenerator[Event, None]:
        state = TaskState(goal=goal)
        messages = self._build_messages(goal, history)

        while state.iterations < self.max_iterations:
            # 上下文压缩检查
            messages = self.context.compress_if_needed(messages)

            # Act: 调 LLM
            response = await self.llm.ainvoke(messages)
            yield Event("token", response.content)

            if not response.tool_calls:
                yield Event("done", response.content)
                return

            # Act: 执行工具（复用 graph.py 的 _execute_single_tool）
            results = await self._execute_tools(response.tool_calls)
            yield Event("tool_results", results)

            # Observe: 程序化检查结果
            observation = self._observe(results, state)

            # Reflect: 观察结果注入 prompt，更新状态
            state.update(observation)
            messages = self._reflect(messages, response, results, observation)

            # 多维退出判断
            if self._should_stop(response, observation, state):
                final = await self._generate_final_answer(messages, state)
                yield Event("done", final)
                return

            state.iterations += 1
```

### 3.2 五个关键模块

**TaskState — 目标驱动的结构化状态**
```python
@dataclass
class TaskState:
    goal: str                     # 用户原始目标
    completed_steps: list[str]    # 已完成的步骤描述
    data_collected: dict          # 已收集的结构化数据
    tool_call_history: list       # 调了哪些工具 + 关键结果
    iterations: int               # 当前轮次
    status: str                   # planning | executing | done
```

**Observation — 程序化检查（非 LLM 猜测）**

检查每个工具结果：error? 空? 重复? 有效? 返回结构化 Observation，注入 prompt 让 LLM 决策下一步。

**StopDecision — 多维退出条件**

1. LLM 没调工具（主动结束）
2. 陷入循环（重复调同一工具且结果没变化）
3. 数据已够回答问题
4. 达到迭代上限

**ContextManager — 自动压缩**

超预算时对早期消息做 LLM 摘要，保留最近 N 条原文。

**Plan + TodoWrite — 可观测规划**

Agent 内部维护步骤清单，前端渲染为 TodoWrite 进度条。

### 3.3 Prompt 设计

4 个角色 Prompt → 1 个 Agent Prompt：

```python
AGENT_PROMPT = """你是 LineMind 智能工单助手。你有 12 个工具。

## 工作方式
每条系统消息包含上一轮工具执行的 [观察结果]。
基于观察决定：还需要什么？还是已经够了？

## 核心规则
- 查询工单 → query_tickets，不要直接 execute_sql
- 统计/分布 → analyze_tickets
- 历史方案 → search_solutions（先内后外）
- 画图 → 先拿数据再调 execute_python
- 工具失败 → 换方法，不反复重试
- 数据够了 → 输出答案，不过度探索
- 不确定 → 继续查，但一轮不超过 3 个工具

## 工具清单
{tools}

## 当前任务
目标: {goal}
已完成: {completed}
计划: {plan}"""
```

---

## 四、评测重新设计

### 4.1 三类题

**A 类：单步直达（~15 题）** — 验证基础能力不退化
```
"工单WO-20260506-002的详细信息？"
→ 调 get_ticket_detail → 返回 → 不继续
→ 测什么: Agent 知道什么时候该停
```

**B 类：真正多步（~25 题）** — 核心指标
```
"找出最近一周的紧急设备故障工单，分析涉及的设备型号，
 然后查一下这些型号有没有历史维修方案。"
→ query_tickets → 分析设备列表 → search_solutions 多个 → 综合
→ 测什么: Plan-Act-Observe-Reflect 全链路
```

**C 类：需要内部决策（~10 题）** — 区分 Agent 和 Workflow
```
"查一下质量异常工单里有没有跟40Cr钢材相关的。
 有就推荐处理人；没有就看看这周有没有新的质量异常。"
→ 第一步结果决定第二步动作
→ 测什么: 动态决策，非预编程路径
```

### 4.2 新指标

| 旧指标 | 新指标 | 说明 |
|--------|--------|------|
| 路由准确率 | **删除** | 没有 Supervisor 了 |
| 工具 Jaccard | **必要工具覆盖率** | expected_tools 改必要集+可选集，只比对必要集 |
| 无 | **任务完成率**（新增） | 评判最终回答是否满足用户需求 |
| 平均步数 | **步数分布** | 简单题 1-2 步、复杂题 3-5 步 |
| 崩溃率 | **崩溃率** | 不变 |
| 工具执行成功率 | **工具执行成功率** | 保留 |

### 4.3 expected_tools 新格式

```json
{
    "id": "M01",
    "question": "找出紧急设备故障工单，涉及的设备型号有哪些，有没有历史维修方案",
    "category": "multi-hop",
    "difficulty": "hard",
    "required_tools": ["query_tickets_tool", "search_solutions_tool"],
    "optional_tools": ["get_schema_tool", "execute_sql_tool"],
    "min_steps": 3,
    "max_steps": 6
}
```

---

## 五、实施步骤

| # | 步骤 | 内容 |
|---|------|------|
| 1 | 新建 agent_loop.py | AgentLoop 类 + TaskState + Observation + ContextManager + StopDecision |
| 2 | 重写 prompts.py | 4 个角色 Prompt → 1 个 AGENT_PROMPT |
| 3 | 简化 graph.py | 5 节点 → 2 节点（agent + tool_executor） |
| 4 | 删除旧节点 + agent.py | nodes/ 全目录 + 旧 agent.py |
| 5 | 前端适配 | _create_stream 适配新 Event 类型 |
| 6 | 评测集重写 | 新 50 题（A类15 + B类25 + C类10） |
| 7 | 跑评测 | `judge.py -n 50 --seed 42`，对比改前基线 |
| 8 | RAG 回归 | `bench_rag.py`，确认 RAG 指标不变 |

### 不变模块

- `tools.py` — 12 工具 + 断路器 + 重试 + 超时 + 沙箱
- `rag.py` — ChromaDB + FTS5 双通道 RRF
- `database.py` — SQLite 13 表 + 种子数据
- `mcp_server.py` — MCP stdio 服务
- `scheduler.py` — 定时告警
- `config.py` / `logger.py` — 基础设施

---

## 六、面试定位

**两个强项 + 一个亮点：**

| 角色 | 模块 | 面试能说什么 |
|------|------|------------|
| 强项 1 | RAG 检索 | 双通道 ChromaDB+FTS5 → RRF 融合，消融实验置信度提升 10.5% |
| 强项 2 | 工具安全 | 12 工具 + 断路器熔断 + 指数退避重试 + Python 沙箱隔离 |
| 亮点 | Agent Loop | while(hasToolCalls) + Plan-Act-Observe-Reflect |

**必答题："为什么从多 Agent 改成单 Agent？"**

> zero2Agent Basic 08 的判断：大多数项目的多 Agent 只是"把 Prompt 拆成几份"。LineMind 的 4-Agent 共享同一个 LLM、同一个执行循环、同一个状态，本质是多角色 Prompt。单 Agent 有更集中的状态管理、更容易调试、行为更可预测。多 Agent 只在真正需要上下文隔离或并行执行时才值得引入——这个项目还没到那个复杂度。

**了解但诚实说没做：** Memory 架构、Context Engine、SubAgent 派生、多渠道路由

---

## 七、学习资源

- [zero2Agent](https://onefly.top/zero2Agent/) — Agent 工程完整教程（离线: `E:\develop\claude\面试准备\_zero2Agent\`）
- [Anthropic Harness Design](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [pi-mono](https://github.com/badlogic/pi-mono) — TypeScript Agent Loop 参考实现
