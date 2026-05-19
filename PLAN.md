# AgentForge — 完整项目优化计划

> 目标：让项目从"带工具调用的 LLM App"升级为真正的 Agent 系统，拿到实习面试

---

## 一、当前项目状态

### 1.1 分层成熟度评估

| 层 | 评分 | 现状 |
|----|:---:|------|
| Agent | ⭐ | 最弱。5 Agent 路由分发 = 多角色 Prompt，不是多 Agent。没有 Agent Loop，没有 Planning，没有 Reflection |
| Tools | ⭐⭐⭐⭐ | 12 工具 + 断路器 + 重试 + 超时 + Python 沙箱。透传层冗余 |
| RAG | ⭐⭐⭐⭐ | 双通道（ChromaDB + FTS5 → RRF）+ 消融实验。无增量索引 |
| Eval | ⭐⭐⭐⭐ | 全客观指标 + Jaccard + 50 题 6 类。缺 multi-hop 题 |
| Data | ⭐⭐⭐ | 1219 行单体文件。Schema 设计好、种子数据好。无连接池、无迁移 |
| Config | ⭐⭐⭐ | 正常。缺 .env.example 和启动验证 |
| Frontend | ⭐⭐ | 1246 行单文件。CSS/JS 嵌入 Python |
| Prompts | ⭐⭐ | 死代码已清。没有 Agent 行为模式 |

### 1.2 核心问题

> Agent 和 Chatbot 的唯一区别：当模型返回 tool_calls 时，执行工具并继续循环，而不是直接结束。（zero2Agent 02章）

你的项目没有这个循环。Agent 每次只调一个工具就停。

---

## 二、面试定位策略

**不是"什么都会"。是"两个强项 + 一个亮点"。**

| 角色 | 模块 | 面试能说什么 |
|------|------|------------|
| 强项 1 | RAG 检索 | 双通道 + RRF + 消融实验数据 |
| 强项 2 | 工具安全 | 沙箱 + 断路器 + 重试 + 超时 |
| 亮点 | Agent Loop | 80 行自实现 while(hasToolCalls) |

面试官问 RAG → 你是专家。问工具安全 → 你是专家。问 Agent 本质 → 你能写代码。问 Memory/Context Engine → 诚实说在计划里。

---

## 三、优化清单（按面试权重排）

### Tier 0 — 决定简历过不过筛（必须先做）

| # | 改什么 | 为什么 | 耗时 |
|---|--------|--------|:---:|
| 1 | README 重写 | "制造业工单系统"→ HR 关掉。"闭环 Agent 执行框架"→ HR 继续看 | 1h |
| 2 | 简历条目重写 | 聚焦 RAG + 工具安全 + Agent Loop。数字：12 工具 0 崩溃、置信度 +10.5%、50 题评测 | 30min |

### Tier 1 — 决定面试过不过第一轮

| # | 改什么 | 为什么 | 耗时 |
|---|--------|--------|:---:|
| 3 | agent_loop.py | Agent 和 Chatbot 本质区别。80 行代码能讲 | 2天 |
| 4 | multi-hop 评测 10 题 | 验证 Agent 真正在"多步执行" | 1h |
| 5 | RAG 消融数据写进 README | 双通道 vs 单通道对比表 | 30min |
| 6 | prompts.py 重写 | Plan-Act-Observe-Reflect 注入 | 1h |
| 7 | graph.py 简化 | 7 节点 → 3 节点 | 1h |

### Tier 2 — 面试能聊深

| # | 改什么 | 为什么 | 耗时 |
|---|--------|--------|:---:|
| 8 | TodoWrite 步骤清单 | Claude Code 同款。面试官一听知道读过源码 | 1h |
| 9 | 前端展示 Plan/Reflect | 面试能截图：Agent 规划了 3 步、正在执行第 2 步 | 2h |
| 10 | 沙箱安全测试 3 个 | "怎么防 prompt injection？"→ 测试证明 | 1h |
| 11 | memory.py | 三层记忆：会话内 / 跨会话 / RAG | 2h |

### Tier 3 — 加分但不致命

| # | 改什么 | 为什么 |
|---|--------|--------|
| 12 | 飞书 Webhook | 企业集成亮点 |
| 13 | .env.example | clone 下来能跑 |
| 14 | Data 层拆分 | 1219 行 → 3-4 文件 |
| 15 | Frontend 拆分 | 1246 行 → 3 文件 |
| 16 | RAG 增量索引 | 不用每次 Nuke & Pave |

---

## 四、学习资源

### 网站爬取内容：`_zero2Agent/` 目录（58 个文件）

### 推荐学习顺序（和 AI 开发并行）

| 阶段 | 先学（zero2Agent） | AI 同时做（项目） |
|------|-------------------|-----------------|
| 1 | Basic 01-03（Agent 定义、Workflow vs Agent、核心组成） | README 重写 |
| 2 | Basic 05 Tool Calling | 梳理 12 工具 |
| 3 | Basic 06 Memory | memory.py |
| 4 | Basic 07 Planning/Reflection/RAG | prompts.py 重写 |
| 5 | Basic 08 单 vs 多 Agent | graph.py 简化 |
| 6 | OpenClaw 01-02 + Claude Code 01 | **agent_loop.py** |
| 7 | Claude Code 03 TodoWrite | TodoWrite 模式 |
| 8 | OpenClaw 05 Context Engine | 上下文管理 |
| 9 | Agent Interview 模块 | 面试准备 |

### 学习参考网站

- [zero2Agent](https://onefly.top/zero2Agent/) — Agent 工程完整教程（爬取内容在 _zero2Agent/）
- [Anthropic Harness Design](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)

---

## 五、Agent Loop 核心（必做）

```python
# backend/agent_loop.py — ~80行

class AgentLoop:
    """while(hasToolCalls) — Agent 和 Chatbot 的唯一区别"""

    def __init__(self, llm, tools, max_iterations=8):
        self.llm = llm
        self.tools = tools
        self.max_iterations = max_iterations

    async def run(self, goal: str, history: list):
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

`_execute_with_safety` 直接复用当前 `graph.py` 的 `_execute_single_tool`。

### Prompt 注入 Planning

```python
AGENT_PROMPT = """你是 LineMind 智能工单 Agent。

## 执行模式（Plan → Act → Observe → Reflect）
1. Plan: 判断需要几步、用哪些工具
2. Act: 调用工具执行
3. Observe: 检查结果——完整吗？有 error 吗？
4. Reflect: 够了吗？不够 → 继续。够了 → 输出答案

## 规则
- 能一步完成的不拆两步
- 工具失败 → 换方法，不放弃
- 信息不足 → 继续查，不编造
- 数据够了就停

## 状态
目标: {goal} | 已完成: {completed_steps} | 剩余轮次: {remaining}
"""
```

### 图简化

7 节点 → 3 节点：
```
agent_node → tool_executor_node → agent_node → END
```

砍掉 Supervisor、Query/Analyze/Knowledge/Reporter 节点。保留 tool_executor_node。

### 不改的模块

RAG 双通道、12 工具 + 断路器 + 沙箱、Streamlit 前端 + 流式、MCP server、评测脚本

---

## 六、文件结构（改造后）

```
linemind/
├── backend/
│   ├── agent_loop.py      ← ★ 新增：Agent Loop
│   ├── tools.py           ← 保留
│   ├── rag.py             ← 保留
│   ├── memory.py          ← 新增
│   ├── evaluator.py       ← 新增（可选）
│   ├── database.py        ← 保留
│   ├── graph.py           ← 简化：3节点
│   ├── prompts.py         ← 重写：1个 AGENT_PROMPT
│   ├── config.py          ← 保留
│   └── mcp_server.py      ← 保留
├── frontend/
│   └── app.py             ← 小改
├── eval/
│   ├── judge.py           ← 保留
│   ├── bench_rag.py       ← 保留
│   └── test_queries.json  ← 加 multi-hop
├── _zero2Agent/           ← 网站爬取内容（学习资料）
├── README.md              ← 重写
├── AGENTS.md              ← Claude 入口
├── PLAN.md                ← 本文档
├── CHANGELOG.md           ← 保留
├── HANDOFF.md             ← /clear 恢复
└── requirements.txt
```

---

## 七、执行顺序

```
第一步：README 重写 (1h)             Tier 0
第二步：agent_loop.py (2天)          Tier 1 核心
第三步：prompts.py 重写 (1h)         Tier 1
第四步：graph.py 简化 (1h)           Tier 1
第五步：multi-hop 评测 (1h)          Tier 1
第六步：RAG 数据写进 README (30min)  Tier 1
第七步：TodoWrite (1h)               Tier 2
第八步：前端展示 Plan/Reflect (2h)   Tier 2
第九步：沙箱安全测试 (1h)             Tier 2
第十步：memory.py (2h)               Tier 2
```

---

## 八、面试准备（项目完成后）

资源：`_zero2Agent/learn-agent-interview.txt`（蚂蚁/阿里/字节/腾讯 Agent 面试 15 大维度）

**必问 5 题（能答深）**：Agent vs Chatbot 区别、为什么单 Agent 替代多 Agent、RAG 双通道为什么更好、工具调用失败处理、沙箱安全

**了解但诚实说没做**：Memory 架构、Context Engine、Multi-Agent 协作

---

## 九、简历条目

> **AgentForge — 闭环 Agent 执行框架** (2026.04-2026.06)
> - 实现 Agent Loop 核心循环(while(hasToolCalls))，注入 Plan-Act-Observe-Reflect 执行模式
> - 双通道混合检索（ChromaDB 向量 + SQLite FTS5 → RRF 融合），消融实验置信度提升 10.5%
> - 自研 Python 沙箱（AST 分离 + 临时目录隔离），防 prompt injection
> - 工具编排层：12 工具 + 断路器熔断 + 指数退避重试 + per-tool 超时，0 崩溃
> - 50 题自动化评测：Jaccard 工具匹配 + 执行成功率 + 多步任务完成率
