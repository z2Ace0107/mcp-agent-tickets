# AgentForge — 项目转型完整计划

> 基于 zero2Agent 全站 39 章 + Anthropic/Google DeepMind 2026 年 Agent 架构研究制定

---

## 一、认知复位

### 1.1 你当前的位置

| Agent 必要模块（zero2Agent 08章） | 状态 |
|----------------------------------|:---:|
| Goal（目标管理） | ❌ |
| State（显式状态） | ❌ |
| Model（大模型） | ✅ DeepSeek |
| Tools（外部能力） | ✅ 12工具 + 断路器 + 沙箱 |
| Memory（记忆） | ⚠️ 仅有消息历史 |
| Planner（决策） | ❌ |
| Evaluator（评估） | ❌ |
| Guardrails（护栏） | ⚠️ 断路器有，缺输出校验 |

### 1.2 核心问题

网站原话：

> "如果单 Agent 还没做稳，多 Agent 大概率只会把问题复制并放大。一个常见误区：把 Prompt 分角色，就以为自己做了多 Agent。"

> "Agent 和 Chatbot 的区别只有一个：当模型返回 tool_calls 时，执行工具并继续循环，而不是直接结束。"

你现在的 5 Agent 路由分发 = 多角色 Prompt，不是多 Agent。Agent Loop 才是灵魂。

---

## 二、学习路径

### 阶段 1: 概念地基（zero2Agent basic 8章）— 1-2天

精读顺序：什么是Agent → Workflow vs Agent → 核心组成 → Demo不稳定的原因 → Tool Calling → Memory → Planning/Reflection/RAG → 单Agent vs 多Agent

**关键收获**：能区分 Agent/Workflow/LLM App，知道 8 个模块的职责边界。

### 阶段 2: Agent Loop 源码（OpenClaw + Claude Code）— 2-3天

| 章节 | 收获 |
|------|------|
| OpenClaw 01: 为什么要自己写 Agent | 框架 vs 生产级方案差异 |
| OpenClaw 02: Agent Loop 核心循环 | 30行伪代码 = 所有Agent本质 |
| Claude Code 01: Agent Loop | Python实现 |
| Claude Code 02: Tool Use | 工具执行模式 |
| Claude Code 03: TodoWrite | 任务规划与跟踪 |

### 阶段 3: 动手项目（5-7天）

按本计划第三部分执行。
  
### 阶段 4: 面试备战（Agent Interview 模块）— 2天

对照网站 15 大考察维度 + 公司偏好速查表逐题演练。

---

## 三、项目改造方案

### 3.1 核心改动：实现 Agent Loop

```python
# backend/agent_loop.py — 整个项目的灵魂，~80行

class AgentLoop:
    """Agent 核心循环。Agent 和 Chatbot 的唯一区别就在这里。"""
    
    def __init__(self, llm, tools, max_iterations=8):
        self.llm = llm
        self.tools = tools
        self.max_iterations = max_iterations
    
    async def run(self, goal: str, history: list) -> AsyncGenerator[Event, None]:
        state = TaskState(goal=goal)
        messages = history + [SystemMessage(content=AGENT_PROMPT.format(
            goal=goal, tools=self._tool_list()))]
        
        while state.iterations < self.max_iterations:
            response = await self.llm.ainvoke(messages)
            yield Event("message", response.content)
            
            if not response.tool_calls:
                yield Event("done", response.content)
                return
            
            results = await self._execute_with_safety(response.tool_calls)
            yield Event("tool_results", results)
            
            messages.append(response)
            messages.extend(results)
            state.iterations += 1
```

### 3.2 Prompt 注入 Planning

```python
AGENT_PROMPT = """你是 LineMind 智能工单 Agent。你有工具和记忆，围绕目标持续推进。

## 你的工具
{tools}

## 执行模式（Plan → Act → Observe → Reflect → Loop）
1. Plan: 判断需要几步、用哪些工具
2. Act: 调用工具执行当前步骤
3. Observe: 检查工具返回——完整吗？有 error 吗？
4. Reflect: 数据够了吗？不够 → 继续 Plan → Act。够了 → 输出最终答案

## 核心规则
- 能一步完成的不拆两步
- 工具失败 → 换方法重试，不要放弃
- 信息不足 → 继续查，不要编造
- 数据够了就停，不要反复调同一个工具
- 用户要图表 → 先拿数据 → 再调 execute_python 画图

## 当前状态
目标: {goal}
已完成: {completed_steps}
剩余轮次: {remaining_iterations}
"""
```

### 3.3 图结构简化

从 7 节点 → 3 节点：

```python
# graph.py
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tool_executor", tool_executor_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", route, {
    "tool_executor": "tool_executor",
    "END": END
})
workflow.add_edge("tool_executor", "agent")
```

**砍掉**：Supervisor、Query Agent、Analyze Agent、Knowledge Agent、Reporter。
**保留**：tool_executor_node（断路器/重试/超时机制完整复用）。

### 3.4 加显式状态跟踪

```python
@dataclass
class TaskState:
    goal: str
    plan_steps: list[str] = field(default_factory=list)
    current_step: int = 0
    completed: list[dict] = field(default_factory=list)
    iterations: int = 0
```

注入 Prompt，替代从消息历史"猜"状态。

### 3.5 内存模块

```python
# backend/memory.py
class AgentMemory:
    def load_context(self, goal: str, history: list) -> list:
        """组装上下文：最近 N 轮对话 + RAG 检索结果 + 全局状态"""
        pass
    
    def save(self, messages: list):
        """持久化关键信息"""
        pass
    
    def compact(self, messages: list) -> list:
        """上下文快满时压缩早期对话"""
        pass
```

### 3.6 评测升级

```json
// eval/test_queries.json — 新增 multi-hop 题
{
  "id": "M01",
  "question": "最近一周的紧急设备故障工单，各自查历史解决方案，汇总给我",
  "expected_tools": ["query_tickets_tool", "search_solutions_tool"],
  "min_steps": 3,
  "difficulty": "hard",
  "category": "multi-hop"
}
```

加 10 道真正需要 2-4 步执行的题。评测指标保留 Jaccard + 执行成功率 + 步数/耗时 + 崩溃率。

---

## 四、面试叙事

### 4.1 1 分钟自我介绍

> "我做了 AgentForge，一个基于 Agent Loop 模式的闭环执行框架。核心实现了一个 80 行的 Agent Loop——while(hasToolCalls) 循环驱动任务持续推进直到完成。上面加了 Planning（Prompt 内 Plan-Act-Observe-Reflect）、RAG 双通道混合检索、Python 安全沙箱、工具断路器机制。50 题评测覆盖单步和多步场景，工单数据做验证。"

### 4.2 必问 5 题

| 问题 | 你的答案要点 |
|------|------------|
| Agent 和 Chatbot 的区别 | Agent Loop 有内层循环——检测到 tool_calls 时继续执行并回调 LLM。本质是 while(hasToolCalls)。我 80 行代码实现了这个。 |
| 为什么从多 Agent 改成单 Agent | 多 Agent 的分工优势在我的场景里没体现。先做扎实单 Agent + Planning+Reflection 闭环，比过早拆多 Agent 更合理。保留了拆分能力。 |
| RAG 双通道为什么更好 | 向量语义 + FTS5 关键词 → RRF 融合。中文口语查询有 LIKE 兜底。消融实验置信度提升 10.5%，英文/数字术语查询提升 25%。 |
| 工具调用失败怎么处理 | 断路器熔断（3次连续失败）、指数退避重试（200/400/800ms）、per-tool 超时、降级返回。统一在 tool_executor 层实现。 |
| 沙箱怎么防 prompt injection | AST 语法树分离 setup 和 expression。临时目录隔离（savefig 重定向）。`__import__`/`eval`/`exec` 不在 safe_locals。pio.renderers.default="json" 禁浏览器弹出。 |

---

## 五、不改的模块

| 模块 | 处理 |
|------|------|
| RAG 双通道 + RRF + 消融实验 | 不动——最好模块 |
| 12工具 + 断路器/重试/超时/沙箱 | 不动——Agent Loop 的 _execute_with_safety 复用 |
| Streamlit 前端 + 流式 | 小改——适配 Agent Loop Event 流 |
| MCP server | 不动 |
| 50题评测 | 加 multi-hop 题，保留客观指标 |
| 种子工单数据 | 不动 |

---

## 六、文件结构（改造后）

```
linemind/
├── backend/
│   ├── agent_loop.py      ← ★ 新增：Agent Loop 核心
│   ├── tools.py           ← 保留
│   ├── rag.py             ← 保留
│   ├── memory.py          ← 新增：记忆管理
│   ├── evaluator.py       ← 新增：输出评估
│   ├── database.py        ← 保留（死表已清）
│   ├── graph.py           ← 简化：3节点图
│   ├── prompts.py         ← 重写：1个 AGENT_PROMPT
│   ├── config.py          ← 保留
│   └── mcp_server.py      ← 保留
├── frontend/
│   └── app.py             ← 小改
├── eval/
│   ├── judge.py           ← 保留
│   ├── bench_rag.py       ← 保留
│   └── test_queries.json  ← 加 multi-hop
├── README.md              ← 重写
├── AGENTS.md              ← 更新
├── PLAN.md                ← 本文档
├── CHANGELOG.md           ← 保留
└── requirements.txt       ← 保留
```

---

## 七、执行顺序

```
第1天：概念学习（Agent Basic 8章 + OpenClaw 01-02）
第2天：源码学习（Claude Code 01-03 + OpenClaw 03-05）
第3天：实现 agent_loop.py + 重写 prompts.py
第4天：简化 graph.py + 实现 memory.py
第5天：实现 evaluator.py + 前端适配
第6天：评测升级（加 multi-hop）+ 跑全量
第7天：文档重写 + 面试准备
```
