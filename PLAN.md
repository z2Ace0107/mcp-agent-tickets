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

## 二、完整架构

### 2.1 项目分层总览

```
┌─ Presentation Layer ─────────────────────────────────────┐
│  frontend/app.py                                          │
│  Streamlit UI + 流式事件消费 + ReAct 面板 + 图表渲染       │
│  事件: progress / token / tool_call / tool_result / done  │
└──────────────────────┬───────────────────────────────────┘
                       │ run_agent_stream(user_input, history)
                       ▼
┌─ Orchestration Layer ────────────────────────────────────┐
│  backend/agent.py   → 薄壳入口                            │
│  backend/graph.py   → LLM 工厂 + 工具注册 + 流式转发       │
│  职责: 创建 LLM → 注册 14 工具 → 实例化 AgentLoop → 迭代事件│
└──────────────────────┬───────────────────────────────────┘
                       │ AgentLoop.run(goal, history)
                       ▼
┌─ Agent Core ─────────────────────────────────────────────┐
│  backend/agent_loop.py                                    │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ while state.iterations < max_iterations:            │ │
│  │   1. Act: LLM 决策（调什么工具）                     │ │
│  │   2. Observe: 程序化检查工具结果                     │ │
│  │   3. Reflect: 观察注入 prompt，更新状态              │ │
│  │   4. Compact: 上下文超预算时压缩                     │ │
│  │   5. ShouldStop? → 最终回答 : 继续循环               │ │
│  └─────────────────────────────────────────────────────┘ │
│  核心类: TaskState / Observation / AgentLoop              │
│  核心函数: _should_stop / _observe_tool_result            │
└──────┬──────────────────┬────────────────────────────────┘
       │ LLM call         │ Tool execution
       ▼                  ▼
┌─ Model ──────┐  ┌─ Tools Layer ─────────────────────────┐
│ DeepSeek     │  │ backend/tools.py (12 原有 + 2 新增)    │
│ v4-flash     │  │ backend/graph.py (_execute_single_tool)│
│ ChatOpenAI   │  │ backend/knowledge_base.py (设备手册+SOP)│
└──────────────┘  │                                       │
                  │ 安全: 断路器 / 重试 / 超时 / 沙箱       │
                  │ 限频: 每工具调用上限 (v5.1 Phase 3)     │
                  └──────────────┬────────────────────────┘
                                 │
                  ┌──────────────┴────────────────────────┐
                  │ Data Layer                            │
                  │ backend/database.py (SQLite 13 表)     │
                  │ backend/rag.py (ChromaDB + FTS5)       │
                  └───────────────────────────────────────┘
```

### 2.2 Agent 层七模块拆解

#### Goal（目标）

| 维度 | 当前实现 | 位置 |
|------|---------|------|
| 输入 | 用户原始文本作为 `goal` 参数 | `agent_loop.py:379` → `TaskState(goal=goal)` |
| 传递 | **双重传递**: SystemPrompt `{goal}` + HumanMessage(goal) 在消息末尾 | `agent_loop.py:_build_system_prompt` + `_assemble_context` |
| 改写 | 不做改写。Agent 自己从模糊表达推断意图，这是 Agent 的核心能力 | — |

**设计原则：** Goal 不预加工。LLM 通过 prompt 理解用户意图，通过工具探索来补充模糊部分。

---

#### State（状态）

| 维度 | 当前实现 | 位置 |
|------|---------|------|
| 结构 | `TaskState` dataclass（6 字段） | `agent_loop.py:41-57` |
| goal | 用户原始问题 | 设置后不变 |
| completed_steps | 每轮完追加 `"第N轮: X个工具"` | `state.mark_step_complete(...)` |
| data_collected | **定义了但从未写入** — 形同虚设 | v5.1 Phase 1 修复 |
| tool_call_history | 每次调工具追加 `{tool_name, args, has_error}` | 工具执行段 |
| iterations | 每轮 +1 | `state.iterations += 1` |
| status | planning → executing → done | `mark_step_complete` / `mark_done` |

**v5.1 优化：** 
- `data_collected` 真正用起来：每次工具成功返回后，把关键数据（条数、关键字段摘要）写入
- 为 Context Engine 的 History Digest 提供结构化数据源

---

#### Model（模型）

| 维度 | 当前实现 | 位置 |
|------|---------|------|
| LLM | DeepSeek v4-flash，ChatOpenAI 兼容接口 | `graph.py:_create_llm()` |
| 参数 | temperature=0.1, max_tokens=4096, streaming=True | 从 `config.py:get_settings()` 读取 |
| thinking | `extra_body={"thinking": {"type": "disabled"}}` | 为兼容性关闭 |
| tool_choice | 循环中 auto，最终回答 `tool_choice="none"` | `agent_loop.py:397` + `336` |

**设计原则：** 单模型驱动。不引入多模型路由（那是 Over-engineering）。DeepSeek 的非确定性单次执行差异是行业普遍问题，通过 StopDecision 程序化兜底来解决。

---

#### Tools（工具）

| 维度 | 当前实现 | 位置 |
|------|---------|------|
| 注册 | 14 个 LangChain `@tool` 装饰器函数 | `graph.py:54-130` |
| 执行 | `_execute_single_tool(name, args, circuit_state)` | `graph.py:150-188` |
| 安全 | 断路器（3 次熔断）+ 指数退避重试（0.2/0.4/0.8s）+ 超时（10/20/30s）+ Python 沙箱 | `graph.py` 常量段 |
| 限频 | **部分实现**：search_solutions/web_search 各 1 次 | `agent_loop.py:442-461` |
| 新增 | search_equipment_manual, query_inspection_records | v5.1 Phase 1 |

**工具清单（v5.1 目标）：**

| 类别 | 工具 | 调用上限 | 
|------|------|:---:|
| 查询 | query_tickets_tool | 不限 |
| 查询 | get_ticket_detail_tool | 4 |
| 查询 | execute_sql_tool | 5 |
| 查询 | get_schema_tool | 不限 |
| 分析 | analyze_tickets_tool | 2 |
| 分析 | recommend_tickets_tool | 不限 |
| 检索 | search_solutions_tool | 1 |
| 检索 | web_search_tool | 1 |
| 检索 | search_equipment_manual ★ | 2 |
| 检索 | query_inspection_records ★ | 3 |
| 操作 | update_ticket_status_tool | 不限 |
| 操作 | assign_ticket_tool | 不限 |
| 操作 | add_ticket_reply_tool | 不限 |
| 可视化 | execute_python_tool | 2 |

---

#### Memory — Short-term（会话记忆）

| 维度 | 当前实现（v5.0） | v5.1 目标 |
|------|-----------------|-----------|
| 结构 | 扁平 messages 列表：`[SystemPrompt, History..., HumanMessage]` | **三层分层** |
| 历史 | `_build_initial_messages` 取最近 6 条原文 | **History Digest**：含压缩后骨架 |
| 轮次边界 | `HumanMessage(goal)` 标记当前问题 | + 显式 `[历史对话摘要]` 分隔符 |
| 压缩 | `_compress_messages`: 超 12000 字裁剪 | **Context Engine**：基于测量数据定参数 |
| 工具结果 | `_truncate_tool_result`: 截 1500 字 | 保持 |

**三层记忆模型（v5.1 Phase 2 实现）：**

```
Layer 1: SystemMessage     — Agent 角色 + 规则 + 工具清单（静态，每轮复用）
Layer 2: History Digest    — 上轮对话的信息骨架（截前 N 字 + [已压缩] 标记）
Layer 3: Current Turn      — HumanMessage(当前) + AIMessage + ToolMessage(本轮)
```

**为什么不做 Long-term Memory？**

> zero2Agent 06："在大多数 Agent 系统里，先把状态设计清楚，比急着做长期记忆更重要。很多所谓 memory 问题，本质上是 state 没设计好。" LineMind 的"记住上一个查询的结果"靠的是前端 `chat_history` 传入，LLM 从上下文推断——这是 Short-term Memory 的范畴。跨会话的长期偏好、用户习惯挖掘属于另一个项目。

---

#### Planner / Policy（决策）

| 维度 | 当前实现 | 位置 |
|------|---------|------|
| 规划 | 固定 4 步占位符：`["理解问题", "收集数据", "分析/检索", "输出答案"]` | `agent_loop.py:384-387` |
| 工具选择 | LLM 根据 SystemPrompt + Observation 自由决策 | Prompt 铁则 + observation_text 引导 |
| 停止判断 | 4 维退出：无工具调用 / 迭代上限 / 陷入循环 / 数据充足 | `agent_loop.py:_should_stop()` |

**停止判断详解：**

| 条件 | 触发规则 | 代码位置 |
|------|---------|---------|
| LLM 主动结束 | `not response.tool_calls` | `agent_loop.py:403` |
| 迭代上限 | `iterations >= max_iterations` (8) | `agent_loop.py:216` |
| 陷入循环 | 连续 3 次同一工具 | `agent_loop.py:_check_stuck()` |
| 数据充足 | 5 次以上有效调用（仅日志不强制退出） | `agent_loop.py:_data_sufficient()` |

**v5.1 优化：**
- 陷入循环阈值可配置：query_tickets 放宽到 4（因为它可能用不同参数多次调用），search 类保持 3
- Planner 让 LLM 首轮生成真实步骤计划（Phase 5）

---

#### Evaluator / Guardrails（评估与约束）

| 层级 | 当前实现 | 位置 |
|------|---------|------|
| **工具输入层** | 无检查。LLM 自由决定参数 | — |
| **工具执行层** | `_observe_tool_result()`: error / empty / duplicate / valid | `agent_loop.py:88-148` |
| **工具频率层** | 两次搜索工具各 1 次 | `agent_loop.py:442-461` |
| **输出层** | `_generate_final_answer()` + 回退提取 | `agent_loop.py:336-356` |
| **评测层** | judge.py 全客观指标 + 崩溃率 | `eval/judge.py` |

**Observation 四态检查：**

```
工具结果 → JSON 解析
  ├── 解析失败 → [ERROR]
  ├── 含 error 字段 → [ERROR]  
  ├── 空列表/空结果 → [EMPTY]
  ├── 与上次同工具同参数 → [DUP]
  └── 正常 → [OK] 返回 N 条数据
```

### 2.3 完整数据流

```
用户输入 "查最近一周设备故障工单"
  │
  ▼
frontend/app.py
  │ chat_history (含之前 2 轮对话)
  ▼
agent.py :: run_agent_stream()
  ▼
graph.py :: run_graph_stream()
  │ _create_llm() → DeepSeek ChatOpenAI 实例
  │ ALL_TOOLS → 14 个 LangChain tool
  │ _execute_single_tool → 工具执行函数
  ▼
AgentLoop.run(goal="查最近一周设备故障工单", history=...)
  │
  ├── _assemble_context(goal, history)
  │     ├── Layer 1: SystemMessage(AGENT_PROMPT)
  │     ├── Layer 2: 压缩后的历史摘要
  │     └── Layer 3: HumanMessage("查最近一周设备故障工单")
  │
  ├── [迭代 0]
  │     ├── LLM.ainvoke(prompt_messages) → AIMessage(tool_calls=[query_tickets_tool])
  │     ├── yield {"type": "token", "content": "我来查询..."}
  │     ├── yield {"type": "tool_call", "tool_name": "query_tickets_tool", ...}
  │     ├── _execute_single_tool("query_tickets_tool", {...}, circuit_state)
  │     │     ├── 断路器检查 → OK
  │     │     ├── 限频检查 → OK
  │     │     ├── tool_func.invoke(args) → JSON result
  │     │     └── 返回 (result_str, meta)
  │     ├── yield {"type": "tool_result", ...}
  │     ├── _observe_tool_result("query_tickets_tool", result, state) → Observation(OK, "2条")
  │     ├── messages.append(response + ToolMessage)
  │     ├── _compact_if_needed(messages) → 未超预算，不压缩
  │     └── _should_stop(response, observations, state) → (False, "继续")
  │
  ├── [迭代 1]
  │     ├── observation_text = "[OK] query_tickets: 返回 2 条数据"
  │     ├── LLM.ainvoke → AIMessage(no tool_calls, content="查到2条工单...")
  │     ├── yield {"type": "token", "content": "查到2条工单..."}
  │     └── 无 tool_calls → yield {"type": "done", "output": "...", "stop_reason": "agent_finished"}
  │
  ▼
graph.py 收集 events → 转发给 frontend
  │ progress → st.write_stream("> 制定计划...")
  │ token → st.write_stream("查到2条...")
  │ step → ReAct 面板渲染
  │ done → st.write_stream(最终回答) + 更新 chat_history
  ▼
用户看到: Markdown 表格 + ReAct 面板(2步)
```

### 2.4 文件结构（v5.1 目标）

```
linemind/
├── backend/
│   ├── __init__.py            ← 应用初始化
│   ├── agent_loop.py          ← ★ Agent 核心循环 + Context Engine
│   ├── tools.py               ← 14 工具函数（不包含 LangChain 装饰）
│   ├── knowledge_base.py      ← ★ 设备手册 + SOP + 巡检记录
│   ├── rag.py                 ← 双通道 RRF 检索
│   ├── database.py            ← SQLite 13 表 + 80+ 种子数据
│   ├── graph.py               ← LLM 工厂 + 工具注册 + 流式转发
│   ├── prompts.py             ← AGENT_PROMPT + FINAL_ANSWER_PROMPT
│   ├── agent.py               ← 薄壳入口（对外的 run_agent / run_agent_stream）
│   ├── config.py              ← 配置管理
│   ├── logger.py              ← 日志
│   ├── scheduler.py           ← 定时告警
│   └── mcp_server.py          ← MCP stdio 服务
├── frontend/
│   └── app.py                 ← Streamlit UI
├── eval/
│   ├── judge.py               ← 评测框架
│   ├── bench_rag.py           ← RAG 双通道消融实验
│   └── test_queries.json      ← 50 题评测集
├── test_agent_loop.py         ← Agent Loop 核心测试
├── CHANGELOG.md
├── AGENTS.md
├── PLAN.md                    ← 本文档
└── README.md
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

## 五、v5.0 实施步骤

| # | 步骤 | 状态 |
|---|------|:---:|
| 1 | 新建 agent_loop.py — AgentLoop 类 + TaskState + Observation + ContextManager + StopDecision | ✅ |
| 2 | 重写 prompts.py — 4 角色 Prompt → 1 个 AGENT_PROMPT | ✅ |
| 3 | 简化 graph.py — 5 节点 → AgentLoop 驱动 | ✅ |
| 4 | 删除旧节点 — nodes/ 全目录 + 旧 agent.py + 旧 Prompt | ✅ |
| 5 | 前端适配 — 移除路由徽标、意图识别、死字段 | ✅ |
| 6 | 评测集重写 — 新 50 题（A类15 + B类20 + C类15） | → v5.1 Phase 4 |
| 7 | 跑评测 — `judge.py -n 50 --seed 42` | → v5.1 Phase 6 |
| 8 | RAG 回归 — `bench_rag.py` | → v5.1 Phase 6 |

---

## 六、v5.1 优化计划

> v5.0 测试暴露了三层缺失：数据量不够探索、无 Context Engine、只有 Prompt 软约束。
> v5.1 的核心思路：**数据先行 → 架构适配 → 评测验证**。

### 6.1 实施顺序

| Phase | 内容 | 优先级 | 说明 |
|-------|------|:---:|------|
| 1 | **数据 & 环境扩展** | P0 | 33→80+ 工单 + 知识库（设备手册/SOP/巡检）+ 2 新工具 |
| 2 | **Context Engine** | P0 | 消息分层 + 轮次边界压缩 + 回合内 Compaction。参数基于 Phase 1 实际数据测量 |
| 3 | **Agent 稳定性** | P1 | 工具限频分级 + Turn State 重置 |
| 4 | **评测重写** | P1 | 50 题（A 15 / B 20 / C 15）+ 任务完成率新指标 |
| 5 | **前端优化** | P2 | 回答消失修复 + ReAct 面板美化 |
| 6 | **文档 + 回归** | P1 | CHANGELOG/AGENTS 更新 + 全量测试 |

### 6.2 核心设计

**Context Engine（Phase 2）：**
- 三层消息组装：SystemPrompt → History Digest → Current Turn
- 轮次边界：历史 long assistant 回复压缩为信息骨架（截前 N 字 + 标记）
- 压缩参数通过跑 benchmark 测量确定，不预设值

**数据扩展（Phase 1）：**
- 新增 6 条根因链工单（同一设备反复故障的追溯路径）
- 新增 8 条跨部门联动工单（设备→产线→物料连锁）
- 新增知识库（5 台设备手册 + 6 项 SOP + 60 条巡检记录）
- 新增 2 工具：search_equipment_manual、query_inspection_records

**评测（Phase 4）：**
- A 类 15 题：单步直达（测"知道何时停"）
- B 类 20 题：多步推理（测 Plan-Act-Observe-Reflect 全链路）
- C 类 15 题：动态决策（第一步结果决定第二步，非预编程路径）

### 6.3 不变模块

- `tools.py` — 现有 12 工具（只新增不修改）
- `rag.py` — ChromaDB + FTS5 双通道 RRF
- `database.py` — 现有 13 表（只加数据不改 Schema）
- `mcp_server.py` / `scheduler.py` / `config.py` / `logger.py`

---

## 七、面试定位

**两个强项 + 一个亮点：**

| 角色 | 模块 | 面试能说什么 |
|------|------|------------|
| 强项 1 | RAG 检索 | 双通道 ChromaDB+FTS5 → RRF 融合，消融实验置信度提升 10.5% |
| 强项 2 | 工具安全 | 14 工具 + 断路器熔断 + 指数退避重试 + Python 沙箱 + 程序化限频 |
| 亮点 | Agent Loop | while(hasToolCalls) + Plan-Act-Observe-Reflect + StopDecision |
| 新增 | Context Engine | 三层消息组装 + 轮次边界压缩 + 回合内 Compaction |
| 新增 | 知识库 | 设备手册 + SOP + 巡检记录 + 专用检索工具 |

**必答题："为什么从多 Agent 改成单 Agent？"**

> zero2Agent Basic 08 的判断：大多数项目的多 Agent 只是"把 Prompt 拆成几份"。LineMind 的 4-Agent 共享同一个 LLM、同一个执行循环、同一个状态，本质是多角色 Prompt。单 Agent 有更集中的状态管理、更容易调试、行为更可预测。多 Agent 只在真正需要上下文隔离或并行执行时才值得引入——这个项目还没到那个复杂度。

**了解但诚实说没做：** Memory 架构、Context Engine、SubAgent 派生、多渠道路由

---

## 七、学习资源

- [zero2Agent](https://onefly.top/zero2Agent/) — Agent 工程完整教程（离线: `E:\develop\claude\面试准备\_zero2Agent\`）
- [Anthropic Harness Design](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [pi-mono](https://github.com/badlogic/pi-mono) — TypeScript Agent Loop 参考实现
