# Changelog — LineMind

所有显著变更均记录于此。版本号遵循 `主版本.次版本` 格式。

---

## v5.1 (完成 — 2026-05-24)

### Phase 1: 数据 & 环境扩展 ✅
- **种子数据**: 33→67 条工单（含 6 根因链 + 8 跨部门联动 + 5 模糊描述 + 4 方案对比）
- **知识库**: 5 设备手册 + 6 SOP 检查清单 + 22 条巡检记录
- **新工具**: `search_equipment_manual`, `query_inspection_records`
- **TOOL_CN_MAP**: 14 工具中文名映射

### Phase 2: Context Engine ✅
- **_assemble_context**: 三层消息组装（History Digest + 轮次边界压缩 + Current Turn）
- **_compact_tool_results**: 回合内工具结果压缩，超预算时替换最早 ToolMessage
- **参数**: `HISTORY_COMPRESS_THRESHOLD=600`, `HISTORY_KEEP_CHARS=300`, `CONTEXT_BUDGET=12000`

### Phase 3: Agent 稳定性 ✅
- **TOOL_CALL_LIMITS**: 工具调用分级限频表（8 个受限 + 6 个不限）
- **动态工具移除**: 工具达上限后从 `bind_tools()` 中物理移除
- **每轮工具上限**: `MAX_TOOLS_PER_ROUND=2`
- **工具名验证**: 虚构工具名返回 "不存在 + 可用列表"
- **AGENT_PROMPT**: 7 铁则（含执行动作不犹豫）

### Phase 4: 评测重写 ✅
- **54 题**: A 单步 15 / B 多步 20 / C 动态 15 / D 闲聊 4
- **required_tools + optional_tools** 双列表 + min_steps/max_steps
- **三维指标**: 必要工具覆盖率 + 任务完成度 + 步数分布

### Agentic Tracing ✅
- **自动记录**: 每次 run() 自动生成 trace_id 并保存到 SQLite
- **agent_traces + agent_trace_steps** 两张表: 总览 + 细节
- **trace_viewer.py**: CLI 列表/详情/统计三种模式

### Go API 双通道 ✅
- **GO_API_KEY**: OpenCode Go API 优先使用
- **Direct Fallback**: 直连 DeepSeek API 备用
- **配额耗尽**: 报告后下次请求自动切 Direct

### 修复
- **RAG Embedding batch**: DashScope 限制 10 条 → 分批索引，FTS5 回退恢复
- **total_steps 硬编码**: agent_finished 路径从 0 改为实际 len(intermediate_steps)
- **assign_ticket 不调用**: AGENT_PROMPT 新增铁则 7"执行动作不犹豫"

### 评测结果
| 指标 | 结果 |
|------|------|
| 必要工具覆盖率 | 48/54 (88.9%) |
| 任务完成度 | 0.89 |
| 工具执行成功率 | 160/160 (100%) |
| 崩溃率 | 0/54 (0%) |
| 已记录 Trace | 54 条 |

---

## v5.0 (2026-05-21)

### 新增
- **Agent Loop 核心循环**: `agent_loop.py` — Plan → Act → Observe → Reflect
- **StopDecision 退出判断**: 4 维退出（LLM 主动结束 / 迭代上限 / 陷入循环 / 数据充足）
- **Observation 程序化检查**: error / empty / duplicate / valid 四态
- **ContextManager**: 上下文超预算时自动裁剪早期消息
- **程序化工具守卫**: search_solutions / web_search 各只执行一次
- **`test_agent_loop.py`**: 3 项核心测试（退出判断 / 单步 / 多步）

### 增强
- **prompts.py**: 4 角色 Prompt → 1 个 AGENT_PROMPT（含 4 铁则）
- **graph.py**: 5 节点 StateGraph → AgentLoop 驱动，删除路由函数和工具子集
- **前端**: 移除 ROUTE_LABELS / INTENT_LABELS / 路由徽标 / 步骤 0 意图识别
- **上下文污染修复**: 当前问题作为 HumanMessage 放在消息列表最后

### 移除
- **nodes/ 全目录**: supervisor / query / analyze / knowledge 节点
- **旧 agent.py**: 精简为薄壳转发
- **旧 Prompt**: SUPERVISOR / QUERY / ANALYZE / KNOWLEDGE 全部移除
- **convert_markdown_table**: 保留原生 Markdown 表格渲染

---

## v4.0 (2026-05-18)

### 新增
- **流式输出**: LangGraph `stream_mode=["updates", "messages"]` 双通道，Reporter 逐 token 实时输出到前端 `st.write_stream`
- **README v4.0**: 核心数字 + 能力矩阵 + 架构图 + 版本演进对比

### 增强
- Reporter prompt 改为数据优先（数据 80%，建议 1-2 句）
- 评测报告简化：终端只输出路由+工具+崩溃率核心指标

### 移除
- Self-Correction：50 题仅触发 1 次，SQL 成功率已 92.3%，性价比极低

---

## v3.5 (2026-05-18)

### 新增
- **流式输出**: `graph.py` 新增 `run_graph_stream()`，`stream_mode=["updates", "messages"]` 双通道
- **RAG P0**: tickets 表 solution 列补完，`search_solutions` 从 ChromaDB 检索历史方案
- **LLM-as-Judge 三项指标**: 回答相关性（真实 LLM 打分）、SQL 执行成功率、Self-Correction 成功率

### 增强
- 写操作守卫：读查询场景禁止调用 assign/update 工具
- Supervisor 路由边界：计数类问题路由到 query 而非 analyze
- 裁判 prompt 类型感知：不同类别用不同评分标准

---

## v3.3 (2026-05-16)

### 新增
- **5 表星型 Schema**: tickets 加 3 FK 列（equipment_id/line_id/material_id），新建 equipment/production_lines/materials/quality_metrics 四张领域表
- **5-Agent LangGraph**: Supervisor(路由) → Query(6工具)/Analyze(3)/Knowledge(3) → Reporter(execute_python图表)
- **3 个新工具**: get_schema(表结构查询) / execute_sql(只读SQL) / execute_python(沙箱数据分析)
- **Self-Correction**: execute_sql 出错 → 自动注入修正提示 → get_schema→ 重试，最多 2 轮
- **工具子集分组**: 每个 Agent 仅绑定职责相关的工具（不再全量 12 个）
- **节点独立文件**: `backend/nodes/` 目录，supervisor/query/analyze/knowledge/reporter 各一文件
- **种子数据 30+**: 10 台设备/4 条产线/6 种物料/3 条质量指标，当天日期的动态工单

### 增强
- Agent 路由可视化：推理面板步骤 0 显示 Supervisor 路由目标
- 前端重置覆盖全部 12 张表

### 修复
- agent.py 从 550+ 行瘦身至 25 行，移除 legacy 回退代码（git 可回退）
- MCP query_tickets 描述修正为工厂领域类型

---

## v3.2 (2026-05-13)

### 新增
- **告警检测**: 3 条规则（紧急积压 ≥3 / 超 24h 未分配 / 待处理积压 >5），侧边栏徽标展示
- **日报生成**: `generate_report_text()` — Markdown 结构化日报（概览/状态分布/紧急事项/处理人负荷/积压预警/建议）
- **实时监控**: 60s 自动刷新 toggle，侧边栏显示上次检测时间
- **侧边栏工具箱**: 快捷查工单 / 智能提醒 / 一键日报 / 上下文状态指示器

---

## v3.1 (2026-05-12)

### 增强
- UI 轻量化: 全局 14px 字体，对话行高 1.65
- 统计卡片幽灵风格: 数字着色 + 标签灰色
- 侧边栏折叠: 工具箱 expander（v3.2 完善）
- 输入框 min-height 60px + focus 阴影
- 表格 CSS 极简: 去竖线，仅底线，表头浅色小字
- Markdown 表格自动转 Key-Value 列表

---

## v3.0 (2026-05-12)

### 新增
- **预处理路由**: `_preprocess()` — LLM(t=0) 意图分类 + 问题改写 + 三档路由（chat/simple_query/complex）
- **安全防护**: `_execute_tool()` — 指数退避重试 / 10s 超时 / 连续 3 次失败熔断 / 优雅降级
- **证据预算**: `_trim_tool_result()` — 按工具类型裁剪输出，总预算 5200 字符
- **混合记忆**: `_compress_history()` — 超 10 条时 LLM 摘要早期消息，保留最近 4 条原文

### 增强
- **推理可视化升级**: 步骤 0（意图识别）、路由徽标、工具耗时/字符数/裁剪/降级标记
- **Agent 返回值扩展**: `route`、`intent`、`rewritten_query`、`context_info`、每个步骤的 `elapsed`/`original_length`/`trimmed`/`degraded`/`retries`
- **侧边栏**: 上下文状态指示器（压缩/未压缩）

### 修复
- chat 路由徽标不显示
- simple_query 只有 1 轮迭代导致无最终回答
- "已裁剪"徽标 HTML 被转义

---

## v2.0 (2026-05-09)

### 新增
- **9 个 MCP 工具**: query / analyze / update_status / assign / add_reply / get_detail / search_solutions(新) / recommend(新) / web_search(新)
- **MCP 协议**: JSON-RPC stdio 服务器
- **ChromaDB RAG**: 阿里云百炼 text-embedding-v3，7 条已解决工单索引
- **SQLite 持久化**: tickets / ticket_replies / conversations / conversation_messages 四表
- **对话管理**: 创建/切换/删除/置顶/重命名/AI 生成标题
- **种子数据**: 20 条真实工厂工单（设备型号/产线编号/根因分析/经济损失）
- **DeepSeek 极简 UI**: 幽灵卡片、820px 阅读宽度、深色主题 #1b1c21
- **一键备注**: 回复内容快速追加到工单
- **演示模式**: 6 个场景
- **复制/导出 Markdown/下载**

### 增强
- 多工具编排: prompt 规则指导 Agent 链式调用
- 联网搜索: DuckDuckGo（ddgs 包）
- Docker 多阶段构建

---

## v1.0 (2026-05-08)

### 新增
- **MVP 架构**: Streamlit → LangChain Agent (ReAct) → 2 工具（query_tickets、analyze_tickets）
- **Agent 模式**: `llm.bind_tools()` 手动循环（替代 AgentExecutor），最多 5 轮
- **ReAct 可视化**: 前端折叠面板展示 Thought → Action → Observation
- **模拟数据**: 15 条中文工单
- **技术栈**: Python 3.10+ / LangChain / FastAPI / DeepSeek / Streamlit
