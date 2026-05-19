# HANDOFF — AgentForge 项目

> `/clear` 后粘贴此文件内容即可恢复全部上下文。

## 启动

```powershell
cd "E:\develop\claude\项目开发2\LineMind\linemind"
.venv/Scripts/Activate.ps1
streamlit run frontend/app.py   # → http://localhost:8501
```

## 我是谁，项目是什么

AgentForge（原 LineMind）——闭环 Agent 执行框架。工单是验证场景，核心是 Agent Loop + RAG 双通道 + 沙箱工具执行。

## 当前状态

```
v5.0 进行中 — 已完成: 死代码清理 / Reporter移除 / 对话记忆 / 评测重构 / 文档整合
            — 待做: Agent Loop 重写（核心）
```

## 本子已完成

```
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
6f97876 v4.1 P1: Plotly 图表修复 + 流式 thinking 框架
8c931bd v4.1 P1: RAG双通道 + Plotly图表 + query_tickets priority + 多项打磨
```

## 当前架构问题

Agent 层是最弱的一层。现在的 5 Agent 路由分发（Supervisor → Query/Analyze/Knowledge → Reporter）本质是"多角色 Prompt"，不是真正的多 Agent。每次只调一个工具就结束，没有任务规划、没有结果反思。

**核心缺失：Agent Loop。** Agent 和 Chatbot 的唯一区别：`while(hasToolCalls)` 循环——检测到工具调用时继续执行并回调 LLM，而不是直接结束。你的项目没有这个循环。

## 现在要做什么

**实现 Agent Loop，重写 Agent 层。** 不改 RAG、不改工具层、不改前端。只改 Agent 核心。

### 新建文件

**`backend/agent_loop.py`** — 项目灵魂，~80行：

```python
class AgentLoop:
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

`_execute_with_safety` 直接复用当前 `graph.py` 的 `_execute_single_tool`（断路器/重试/超时机制）。

### 重写文件

**`backend/prompts.py`** — 三个 Agent Prompt 合并为一个，注入 Planning：

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
已完成步骤: {completed_steps}
剩余轮次: {remaining_iterations}
"""
```

### 简化文件

**`backend/graph.py`** — 图结构从 7 节点 → 3 节点：

```python
workflow.add_node("agent", agent_node)
workflow.add_node("tool_executor", tool_executor_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", route_agent, {
    "tool_executor": "tool_executor",
    "END": END
})
workflow.add_edge("tool_executor", "agent")
```

### 删除文件

```
backend/nodes/supervisor.py    ← 意图分类由 Agent Prompt 内部完成
backend/nodes/query.py         }
backend/nodes/analyze.py       } 合并为单 Agent，Prompt 自己路由
backend/nodes/knowledge.py     }
```

### 不改的文件

```
backend/tools.py       ← 12工具 + 断路器 + 沙箱，全部保留
backend/rag.py         ← 双通道 RAG，全部保留
backend/database.py    ← 保留
backend/config.py      ← 保留
frontend/app.py        ← 小改适配 Agent Loop Event 流
eval/judge.py          ← 加 multi-hop 题
```

## 关键文档

| 文档 | 内容 |
|------|------|
| [PLAN.md](PLAN.md) | 完整项目计划 |
| [AGENTS.md](AGENTS.md) | Claude 开发入口 |
| [README.md](README.md) | 项目门面 |
| [CHANGELOG.md](CHANGELOG.md) | 版本记录 |

## 知识点速查

- **Agent Loop**: `while(hasToolCalls)` 循环 = Agent 和 Chatbot 的唯一区别
- **Plan-Act-Observe-Reflect**: Agent 的执行闭环
- **RAG 双通道**: ChromaDB 向量 + FTS5 关键词 → RRF 融合
- **断路器**: 3次连续失败熔断，指数退避重试(200/400/800ms)
- **沙箱**: AST 语法树分离 + 临时目录隔离 + Plotly/Matplotlib 双引擎

## 面试可说的三点

1. "我实现了一个 80 行的 Agent Loop——while(hasToolCalls) 循环驱动任务持续执行直到目标完成"
2. "RAG 双通道混合检索：向量语义 + FTS5 关键词 → RRF 融合。消融实验置信度提升 10.5%"
3. "工具执行层：12 工具 + 断路器熔断 + 指数退避重试 + per-tool 超时 + Python 安全沙箱"
