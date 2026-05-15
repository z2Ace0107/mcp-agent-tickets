# Changelog — MCP 智能工单 Agent 系统

所有显著变更均记录于此。版本号遵循 `主版本.次版本` 格式。

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
