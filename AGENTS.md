# AGENTS.md — LineMind

> Claude/OpenCode 会话入口。`/clear` 后读此文件恢复上下文。

## 启动

```powershell
cd "E:\develop\claude\项目开发2\LineMind\linemind"
pip install -r requirements.txt
streamlit run frontend/app.py   # → http://localhost:8501
```

## 项目定位

**闭环 Agent 执行框架**（制造业工单为验证场景）。核心是 Agent Loop + RAG 双通道 + 工具安全层。

## 最近提交

```
4256a94 fix(frontend): 思考过程持久化+自动折叠 + SOP搜索修复
c029b09 fix(frontend): 工具名显示"中文名(原名)"格式 + 清理死代码 + 添加plotly依赖
d92c9c4 feat(tools): Phase 1b+c — 知识库 + 2 新工具
f774a9c feat(data): Phase 1a — 种子数据 33→58 条工单
```

## 当前状态

```
v5.1 — Phase 1 已全部完成 ✅
  ✓ 种子数据: 33→61 条工单（含 6 根因链 + 8 跨部门联动 + 5 模糊描述 + 4 方案对比）
  ✓ 知识库: 5 设备手册 + 6 SOP 检查清单 + 22 条巡检记录
  ✓ 新工具: search_equipment_manual, query_inspection_records
  ✓ TOOL_CN_MAP: 14 工具中文名映射
  ✓ plotly 依赖添加
  ✓ 思考过程持久化: 流式显示 → rerun 后折叠到 expander

➡ 下一步: Phase 2 — Context Engine（P0 优先级）
```

## Phase 2: Context Engine 设计要求

### 核心问题

当前 `_build_initial_messages` 最简：
1. 取最近 6 条消息 → 拼接到 SystemPrompt + HumanMessage + 当前问题
2. 无分层，无压缩，无边界标记
3. 跨问题上下文污染（历史 long reply 影响当前回答）

### 目标架构

三层消息组装（`_assemble_context` 替换 `_build_initial_messages`）：

```
Layer 1: SystemMessage     — Agent 角色 + 规则 + 工具清单（静态，每轮复用）
Layer 2: History Digest    — 上轮对话的信息骨架（截前 N 字 + [已压缩] 标记）  
Layer 3: Current Turn      — HumanMessage(当前) + AIMessage + ToolMessage(本轮)
```

### 具体实现

在 `backend/agent_loop.py` 中：

**1. 测量（先跑再改）**

在 `AgentLoop.run()` 开头加临时日志，收集：
- 单轮工具结果平均大小（ToolMessage.content 长度）
- 多步查询 3-5 步的总 messages 字符数
- 跨问题场景 history 传入的消息大小

**2. 改 `_build_initial_messages` → `_assemble_context`**

```python
def _assemble_context(self, goal: str, chat_history: list | None) -> list:
    """三层消息组装。"""
    msgs = []
    history_msgs = []
    if chat_history:
        for m in chat_history[-6:]:
            role = m.get("role", "")
            content = m.get("content", "")
            if not content:
                continue
            if role == "user":
                history_msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                # 轮次边界压缩：超 HISTORY_COMPRESS_THRESHOLD 则截取前 HISTORY_KEEP_CHARS
                if len(content) > HISTORY_COMPRESS_THRESHOLD:
                    content = content[:HISTORY_KEEP_CHARS] + f"\n\n[已压缩 {len(content)} 字符历史回复]"
                history_msgs.append(AIMessage(content=content))
    if history_msgs:
        msgs.append(SystemMessage(content="[以下为历史对话摘要]"))
        msgs.extend(history_msgs)
    msgs.append(HumanMessage(content=goal))
    return msgs
```

**3. 回合内 Compaction**

在 `AgentLoop.run()` 每轮工具执行后调用：
```python
messages = self._compact_tool_results(messages)
```
- 超 CONTEXT_BUDGET（建议 12000）→ 找最早的 ToolMessage 替换为 `[工具结果已裁剪]`
- 保留 SystemMessage + 最近 6 条原文

### 参数（需先测量再定值）

| 参数 | 建议值（占位） | 定值方式 |
|------|:---:|------|
| `CONTEXT_BUDGET` | 12000 | 多步查询均值的 80% |
| `HISTORY_COMPRESS_THRESHOLD` | 600 | 单轮 assistant 回复中位数的 50% |
| `HISTORY_KEEP_CHARS` | 300 | 保留最小信息量 |
| `MAX_HISTORY_MSGS` | 6 | 保持 |

### 改动的文件

仅 `backend/agent_loop.py`：
- `_build_initial_messages` → `_assemble_context`
- 新增 `_compact_tool_results` 方法
- 新增 `_build_system_prompt` 方法（从 `run()` 抽离）
- `run()` 循环内：每轮工具执行后 compaction

### 验证

```
python test_agent_loop.py    # 3 个核心测试必须全过
```

手动测：
- "CNC-MC-003 的 E01 故障码" → 看是否是独立回答，不受上轮影响
- 连续问 3 个不同问题 → 看是否答非所问

## 架构

```
AgentLoop.run() — while(hasToolCalls) 循环
  ├── Plan → Act(LLM + Tools) → Observe(代码检查) → Reflect
  ├── graph.py: 薄壳（LLM 创建 + 工具执行 + 流式转发）
  └── 14 工具: 12 原有 + 2 新增 (search_manual, query_inspection)

不变模块: tools.py / rag.py / database.py / mcp_server.py / scheduler.py
```

### 事件流（前端理解需要）

graph.py → run_graph_stream → AgentLoop.run() yields:
- `plan`, `token`, `tool_call`, `tool_result`, `step`, `done`

frontend/app.py → _create_stream → text_gen() captures:
- progress 事件 → `> label` blockquote 显示
- token 事件 → 流式输出到 st.write_stream
- done 事件 → metadata["output"] + metadata["steps"] + metadata["thinking_text"]

rerun 后: chat_history 每条 msg 含 `content`（最终回答）+ `thinking`（progress 标签）+ `steps`（工具步骤）

## 开发流程

1. 改代码 → 重启 Streamlit → 浏览器测
2. `python test_agent_loop.py` 核心测试
3. 每步改完 → `git add` + `git commit`
4. 每 Phase 完成后更新 CHANGELOG.md

## 关键文件

| 文件 | 职责 | 状态 |
|------|------|:---:|
| `backend/agent_loop.py` | Agent 核心循环 + Context Engine | **Phase 2 待改** |
| `backend/knowledge_base.py` | 设备手册 + SOP + 巡检 | Phase 1 完成 |
| `backend/database.py` | SQLite 13 表 + 61 条种子数据 | Phase 1 完成 |
| `backend/graph.py` | LLM + 工具注册 + 流式转发 + TOOL_CN_MAP | 稳定 |
| `backend/tools.py` | 14 工具函数 | 稳定 |
| `backend/prompts.py` | AGENT_PROMPT + FINAL_ANSWER_PROMPT | 稳定 |
| `backend/rag.py` | RAG 双通道检索 | 稳定 |
| `frontend/app.py` | Streamlit UI | 稳定 |
| `eval/test_queries.json` | 50 题评测集 | **Phase 4 待改** |
| `eval/judge.py` | 评测框架 | **Phase 4 待改** |

## 已知问题

- RAG embedding API batch size >10 报错（阿里云 DashScope 限制，不影响核心功能）
- 多步测试中 LLM 有时会虚构工具名（search_knowledge_base_tool 不存在），靠 StopDecision 循环检测兜底
- Streamlit 流式输出后页面自动滚到底部，需要后续前端优化处理

## 未来 Phase（Phase 2 之后）

| Phase | 内容 | 优先级 |
|-------|------|:---:|
| 3 | Agent 稳定性 — 工具限频分级 + Turn State 重置 | P1 |
| 4 | 评测重写 — 50 题（A 15 / B 20 / C 15） | P1 |
| 5 | 前端优化 — ReAct 面板美化 | P2 |
| 6 | 文档 + 全量回归 | P1 |

详见 [PLAN.md](PLAN.md) 文档。

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
