# LineMind v4.1 → v5.0 全面优化报告

> 由技术 HR 视角 + Agent 工程视角双审

---

## 一、核心问题：你到底做了什么？

### 现状

简历上写"LineMind — 多 Agent 智能工单系统"，HR 三秒判断：**CRUD 管理系统**。翻篇。

### 可你实际做的是

| 你做了什么 | 简历该怎么说 |
|-----------|------------|
| 5-Agent Supervisor 路由 + 工具子集划分 | **多 Agent 协作框架** — 不是调 API，是设计路由策略 |
| 12 工具带超时/重试/熔断 | **工具编排层** — Agent 工程化安全机制 |
| FTS5 + ChromaDB → RRF 双通道 | **混合检索系统** — 向量语义 + 关键词分词 + 排序融合 |
| AST 沙箱 + 双引擎图表自动捕获 | **安全代码执行器** — prompt injection 防护 |
| 50 题 × 6 类 × 3 级难度 | **自动化评测体系** — 多维度打分 |

**你不是做了一个工单系统。你做了一个多 Agent 平台，用工单场景验证了它。**

### 建议定位

```
项目名：AgentForge（或保留 LineMind）
定位：多 Agent 智能协作平台
验证场景：制造业工单管理
亮点：Supervisor 路由 / 混合检索 / 安全沙箱 / 评测体系
```

**关键叙事转变**：工单从"产品"降级为"Demo 数据"。Agent 框架从"实现细节"升级为"产品本身"。

---

## 二、立即删除清单（面试前必须清掉）

### P0 — 死代码（HR 看到会追问）

| # | 文件 | 删什么 | 行数 | 原因 |
|---|------|--------|:--:|------|
| 1 | `prompts.py` | `SYSTEM_PROMPT` (L8-105) | ~100 | v2.0 ReAct prompt，无调用方 |
| 2 | `prompts.py` | `TOOL_DESCRIPTIONS` (L111-125) | ~15 | v2.0 工具描述，和 graph.py 重复 |
| 3 | `prompts.py` | `FEW_SHOT_EXAMPLES` (L179-204) | ~25 | 从未执行 |
| 4 | `prompts.py` | `CHAT_SYSTEM_PROMPT` (L171) | ~10 | 从未使用 |
| 5 | `prompts.py` | `REPORT_PROMPT` (L210-239) | ~30 | 被 REPORTER_PROMPT 替代 |
| 6 | `prompts.py` | `PREPROCESS_PROMPT` 的 import (graph.py L32) | 1 | 有 import 无调用 |
| 7 | `database.py` | `correction_rules` 表 + 7 条种子 | ~30 | v4.0 砍了 Self-Correction |
| 8 | `database.py` | `agent_actions` 表 | ~15 | 从未被写入 |
| 9 | `database.py` | `sql_templates` 表 + 8 条种子 | ~30 | 无代码路径读取 |
| 10 | `eval/` | `report_v2.0.json` 等 5 个旧 JSON | — | Git 历史已保留 |
| 11 | `frontend/app.py` | `ROUTE_LABELS` 里 `simple_query`/`complex` | ~5 | v3.0 路由名，v4.0 不用 |
| 12 | `frontend/app.py` | `INTENT_LABELS` 里 `recommend`/`search` | ~5 | v4.0 supervisor 不分类这些 |
| 13 | `config.py` | `MCP_SERVER_PORT` | 1 | MCP Server 走 stdio，不是 HTTP |

**合计：约 300 行死代码 + 3 张死表 + 5 个旧文件**

### P1 — 过时文件

| # | 文件 | 处理 |
|---|------|------|
| 14 | `Dockerfile` | 删除或更新到 v4.1 |
| 15 | `backend/mcp_server.py` | `execute_python` 的 MCP 描述缺失 plotly/matplotlib/numpy |

---

## 三、架构优化清单

### 3.1 消除 Agent 节点重复代码（P1）

当前 4 个 Agent 节点各有一份 `_create_llm()` + `llm.invoke()` 样板，80% 重复。

**改为**：在 `nodes/__init__.py` 暴露一个工厂函数：

```python
# backend/nodes/base.py (新文件, ~25行)
def create_agent_node(tools: list, system_prompt: str) -> callable:
    """工厂：生成标准 Agent 节点函数，消除重复。"""
    def agent_node(state: dict) -> dict:
        llm = create_llm()
        llm_with_tools = llm.bind_tools(tools)
        messages = state.get("messages", [])
        rewritten = state.get("rewritten_query", state["user_input"])
        if not messages:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=rewritten),
            ]
        from backend.graph import strip_reasoning_content
        strip_reasoning_content(messages)
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}
    return agent_node

# 使用
query_node = create_agent_node(QUERY_TOOLS, QUERY_AGENT_PROMPT)
analyze_node = create_agent_node(ANALYZE_TOOLS, ANALYZE_AGENT_PROMPT)
knowledge_node = create_agent_node(KNOWLEDGE_TOOLS, KNOWLEDGE_AGENT_PROMPT)
```

**成效**：`query.py`/`analyze.py`/`knowledge.py` 各从 45 行缩减到 5 行。消除 4 份 `_create_llm()` 副本。

### 3.2 修复 `analyze_tickets` priority 盲区（P1）

当前 `database.py:823` 的 `priority_distribution` 硬编码 `["高", "中", "低"]`，遗漏"紧急"。

```python
# 修复：改为动态查询
rows = conn.execute(
    "SELECT priority, COUNT(*) as cnt FROM tickets "
    "GROUP BY priority ORDER BY cnt DESC"
).fetchall()
```

### 3.3 给 `analyze_tickets` 加 `date_range`（P2）

当前要查"今天的分布"必须分别调 `query_tickets` + `analyze_tickets`。加可选参数：

```python
def analyze_tickets(analysis_type: str, date_range: str | None = None):
    # 如果有 date_range，先过滤再统计
```

### 3.4 Supervisor 支持多 Agent 路由（P2）

多跳查询（"查一下质量异常的工单，各自搜一下历史解决方案"）目前无法处理，因为 Supervisor 只路由到单 Agent。

**方案**：Supervisor 输出改为 `route: str | list[str]`。图里加一个循环边，顺序执行多个 Agent 后统一交给 Reporter。

---

## 四、飞书集成计划

### 判断：值得加

理由不是"飞书很火"，而是：
- HR 能看到你**理解企业集成**——不是做了个玩具 Demo
- **零成本展示多通道设计**——同一个 Agent 内核，Web/飞书双入口
- **P2 #5 本来就在计划里**

### 4.1 第一步：群 Webhook 推送（1-2h） 

最轻量的切入。后端加 30 行 + 配置。

```python
# backend/notify.py (新文件)
def send_feishu_report(webhook_url: str, report: dict):
    """推送工单日报到飞书群。支持富文本 + 图片。"""
    import httpx
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"content": f"📋 工单日报 {today}", "tag": "plain_text"}},
            "elements": [
                {"tag": "div", "text": {"content": f"总工单：{report['total']} | 紧急：{report['urgent']} | 待处理：{report['pending']}"}},
                {"tag": "div", "text": {"content": report.get("summary", "")}},
            ]
        }
    }
    httpx.post(webhook_url, json=card)
```

触发方式：定时任务（`schedule` 库已安装）或 Reporter 结束后自动推送。

### 4.2 第二步：紧急工单实时告警（30min）

和日报用同一个 `send_feishu_report`，触发条件改为：
- 新增紧急工单
- 待处理超 7 天工单数量 > 阈值

### 4.3 第三步：飞书 Bot 问答（4-6h）— 可选

飞书开放平台建应用 → 消息回调 → 调 `run_agent()` → 回写飞书消息。

**价值**：证明你的 Agent 不是只能跑在 Streamlit 里，而是有标准 API，任何渠道都能接入。

---

## 五、测试补全计划

### 5.1 最少可接受测试（P0，3-4h）

| 模块 | 测试什么 | 文件 |
|------|---------|------|
| `execute_python` 沙箱 | AST 注入尝试（`__import__`, `eval`, `exec`, `open`） | `tests/test_sandbox.py` |
| `rag.py` 检索 | 已知标注查询命中预期工单 | `tests/test_rag.py` |
| `query_tickets_db` | priority 多值过滤 / date_range 边界 | `tests/test_database.py` |

```python
# tests/test_sandbox.py 示例
def test_sandbox_blocks_import():
    r = execute_python("__import__('os').system('echo pwned')")
    assert r["error"] is not None

def test_sandbox_blocks_eval():
    r = execute_python("eval('1+1')")
    assert r["error"] is not None or "not allowed" in str(r).lower()
```

### 5.2 评测修复（P1）

| 项目 | 现状 | 修复 |
|------|------|------|
| 多跳工具准确率 | 33% (2/6) | 目标 70%+ |
| 工具匹配逻辑 | `issubset` 过于宽松 | 改为 Jaccard ≥ 0.5 |
| LLM-as-Judge 解析 | `re.search(r'[1-5]')` 粗糙 | 结构化输出 `{"score": int}` |
| Q011/Q012 标注 | category: query 但 expected_agent: analyze | 修正为 analyze |
| `bench_rag.py:456` | 死代码 `if 'summary' not in result` | 删除 |

---

## 六、面试叙事重构

### 6.1 简历条目（推荐）

```
AgentForge — 多 Agent 智能协作平台                         2026.04 - 2026.05

• 设计 Supervisor 路由 + 4 专业 Agent 的多 Agent 架构，工具子集划分降低选择复杂度，
  路由准确率 90%（50 题评测集）
• 实现双通道混合检索：ChromaDB 向量语义 + SQLite FTS5 关键词 → RRF 融合排序，
  中文口语查询改写，消融实验置信度提升 10.5%
• 自研 Python 沙箱代码执行器：AST 语法树分离 + 临时目录隔离 + Matplotlib/Plotly 双引擎，
  防止 prompt injection 文件逃逸
• 工具编排层：超时控制 + 指数退避重试 + 断路器熔断，12 工具 0 崩溃
• 50 题自动化评测：6 场景 × 3 难度，路由/工具/相关性/崩溃率多维度打分
• 场景验证：制造业工单数据（30+ 真实设备/产线/物料模型），含 SQL/Web/飞书三通道接入设计
```

### 6.2 面试可能被问到的点 & 预备回答

| 问题 | 预备答案 |
|------|---------|
| "为什么不用 LangGraph 的 ToolNode？" | 我需要自定义超时/重试/熔断策略。LangGraph 内置 ToolNode 没有断路器。但 state graph 的 routing 复用了 LangGraph 的 conditional edges。 |
| "沙箱安全吗？" | AST 级别拦截了 `__import__`、`eval`、`exec` 等，plt.savefig 重定向到 tempfile。不是 100% 安全——`builtins` 没完全清理——但覆盖了 LLM 最可能生成的逃逸路径。 |
| "评测 90% 怎么算的？" | 路由正确性用 label 匹配。工具正确性用 Jaccard 系数。相关性用 DeepSeek 第三方 LLM 盲评。每个维度有独立评分。 |
| "你这个和 LangChain 的 Agent 有什么区别？" | LangChain Agent 是单 Agent + 全量工具列表。我做的是多 Agent + 工具子集划分，每个 Agent 只看 3-6 个工具而不是 12 个。这是工具选择准确率从 74% 提升到 90% 的核心原因。 |
| "种子数据是 AI 生成的？" | 是。但每一张表有关联建模（FK），每一个工单有上下游影响评估、成本计算、标准引用，形成完整的数据闭环，不是随机文本。 |

---

## 七、执行优先级

```
第一优先（面试前必做）：
  ├─ 删死代码（13 项，~300 行 + 3 张表）          [2h]
  ├─ 单元测试（沙箱 + RAG + 数据库，各 3-5 条）    [3h]
  ├─ Agent 节点去重                                 [1h]
  └─ 多跳路由修复                                   [3h]

第二优先（加分项）：
  ├─ 飞书 Webhook 日报推送                          [1.5h]
  ├─ 飞书紧急告警                                    [0.5h]
  ├─ analyze_tickets priority 修复 + date_range     [1h]
  └─ .env.example                                   [5min]

第三优先（锦上添花）：
  ├─ 飞书 Bot 问答                                  [4-6h]
  ├─ Dockerfile 更新                                 [0.5h]
  └─ 前端组件拆分                                    [4h]
```

---

## 八、最终建议

你这个项目的**技术骨架是对的**——Supervisor 路由 + 混合检索 + 安全沙箱 + 评测体系，这四个模块在任何企业 Agent 落地场景里都用得上。

现在的问题不是"做错了什么"，而是"叙事没跟上代码"——你用 80% 的时间做了 Agent 框架，却在简历上把自己描述成 CRUD 开发者。

**删死代码 → 补测试 → 改叙事 → 加飞书**，四步走完，这个项目从"还可以的课程设计"变成"值得面试官追问的 Agent 作品"。
