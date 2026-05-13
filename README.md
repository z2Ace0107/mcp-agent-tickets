# MCP 智能工单 Agent 系统 v3.0

基于 **MCP 协议** 的企业级多智能体工业协管平台，面向制造业工单管理场景，集成 **意图路由、RAG 知识库、安全防护、主动监控** 等能力。

> **v3.0 新增**：意图路由（5类/3档 · 省60% Token）· 9 个 MCP 工具 · 安全防护（重试/超时/熔断）· 证据预算 · 混合记忆（滑动窗口+摘要压缩）· 20 条真实工厂种子数据 · 主动监控告警 · 推理可视化增强

## 功能

| 类别 | 工具 | 说明 |
|:---|:---|:---|
| 🔍 查询 | `query_tickets` | 按类型/状态/日期筛选工单 |
| 📊 分析 | `analyze_tickets` | 类型分布 / 状态统计 / 优先级 / 趋势 / 汇总 |
| ✏️ 操作 | `update_ticket_status` | 更新工单状态 |
| 👤 分配 | `assign_ticket` | 分配工单给处理人 |
| 💬 回复 | `add_ticket_reply` | 为工单添加回复记录 |
| 📋 详情 | `get_ticket_detail` | 查看工单完整信息 + 回复历史 |
| 🧠 RAG | `search_solutions` | ChromaDB 向量检索历史解决方案（阿里百炼 Embedding） |
| 💡 推荐 | `recommend_tickets` | 智能推荐（紧急+积压+分配+关联工单） |
| 🌐 搜索 | `web_search` | DuckDuckGo 联网搜索实时信息 |

### 核心能力

- **意图路由**：5 类意图（查询/分析/推荐/搜索/闲聊）+ 3 档路由策略，闲聊省 60% Token
- **安全防护**：指数退避重试（200→800ms）+ 10s 超时 + 3 次失败自动熔断降级
- **证据预算**：按工具裁剪输出（1500-2500 字符），总预算 5200 字符
- **混合记忆**：滑动窗口（≤10 条）+ 超阈自动 LLM 摘要压缩，保留最近 4 条原文
- **推理可视化**：步骤 0 意图识别 + 工具耗时/裁剪/降级标记
- **对话管理**：SQLite 持久化，支持置顶/分组/搜索/重命名/导出 Markdown
- **主动监控**：侧边栏紧急告警 + 积压预警 + 上下文状态指示

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY（LLM）和 EMBEDDING_API_KEY（阿里百炼向量化）
```

### 3. 启动

```bash
# 前端聊天界面
streamlit run frontend/app.py

# MCP 工具服务器（stdio 模式，可接入 Claude Desktop 等客户端）
python -m backend.mcp_server
```

### Docker

```bash
docker build -t mcp-agent-tickets .
docker run -p 8501:8501 -e DEEPSEEK_API_KEY="your-key" -e EMBEDDING_API_KEY="your-key" mcp-agent-tickets
```

## 架构

```
┌──────────────────────────────────────────────────────────┐
│                    Streamlit 前端                        │
│  路由徽标 / 步骤0意图识别 / 工具耗时 / 证据裁剪标记       │
└──────────────┬───────────────────────────────────────────┘
               │ run_agent()
               ▼
┌──────────────────────────────────────────────────────────┐
│                    Agent 核心层                           │
│  ├─ _preprocess()       ← 意图分类 + 改写 + 路由       │
│  ├─ _compress_history() ← 混合记忆（滑动窗口+摘要压缩） │
│  ├─ _execute_tool()     ← 重试/超时/熔断/证据裁剪      │
│  └─ _extract_intermediate_steps() ← 含元信息提取        │
└──────┬────────────────────┬──────────────────────────────┘
       │                    │
       ▼                    ▼
┌──────────────┐    ┌──────────────────┐
│  工具层 (9)   │    │   知识层          │
│              │    │  ChromaDB         │
│ query/analyze│    │  (阿里百炼        │
│ update/assign│    │   text-embed-3)  │
│ reply/detail │    │  RAG 检索         │
│ search/recomm│    │  7 条已解决工单    │
│ web_search   │    │                  │
└──────┬───────┘    └──────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│                    数据持久层                             │
│  SQLite (tickets + replies + conversations)              │
│  20 条真实工厂工单种子数据                                │
└──────────────────────────────────────────────────────────┘
```

## 对话示例

```
用户: 最近一周有哪些设备故障工单？
Agent: [预处理: intent=query, route=simple_query]
       调用 query_tickets("设备故障", date_range="week")
       → 找到 3 条工单：CNC加工中心主轴异响、注塑机温控失控、焊接机器人焊缝偏移...

用户: 把第一个工单分配给张建国
Agent: [上下文: 上一轮提到了 WO-20260506-002]
       调用 assign_ticket("WO-20260506-002", "张建国")
       → 已分配

用户: 给它加一条回复：主轴轴承已更换，试运行正常
Agent: 调用 add_ticket_reply("WO-20260506-002", "主轴轴承已更换...")
       → 回复已添加
```

## 项目结构

```
mcp-agent-tickets/
├── backend/
│   ├── config.py         # .env 配置管理
│   ├── logger.py         # 结构化日志（控制台 + 文件轮转）
│   ├── database.py       # SQLite CRUD + 20 条真实工厂种子数据
│   ├── tools.py          # 9 个工具业务函数
│   ├── prompts.py        # SYSTEM + PREPROCESS + CHAT + FEW_SHOT 提示词
│   ├── agent.py          # v3.0 Agent（路由/安全/预算/记忆 完整实现）
│   ├── rag.py            # ChromaDB 向量检索（阿里百炼 Embedding）
│   └── mcp_server.py     # MCP stdio 服务器（JSON-RPC 2.0，9 工具）
├── frontend/
│   └── app.py            # Streamlit v3.0 深色主题界面
├── docs/                 # PRD / Tech Design / AGENTS 文档
├── .streamlit/config.toml
├── .env.example
├── requirements.txt
├── test_agent.py         # CLI 集成测试
├── Dockerfile
└── README.md
```

## 技术栈

| 层级 | 技术 |
|:---|:---|
| 前端 | Streamlit（深色主题 #1b1c21） |
| Agent | LangChain + llm.bind_tools() 手动循环 |
| LLM | DeepSeek v4-flash（OpenAI 兼容） |
| Embedding | 阿里云百炼 text-embedding-v3 |
| 向量库 | ChromaDB（持久化） |
| 数据库 | SQLite（工单 + 对话持久化） |
| 联网搜索 | DuckDuckGo（ddgs 包，零 API Key） |
| 协议 | MCP（JSON-RPC 2.0 over stdio） |
| 日志 | Python logging + RotatingFileHandler |
| 部署 | Docker（多阶段构建） |

## 种子数据

20 条真实工厂场景工单，覆盖 7 大类别：
- 设备故障 ×5（CNC主轴异响、注塑机温控、空压机跳闸、AGV碰撞、焊接机器人）
- 质量异常 ×4（钢材硬度、密封圈装反、电镀盐雾、喷漆颗粒物）
- 安全隐患 ×3（安全光幕短接、化学品泄漏、叉车充电氢气）
- 物料短缺 ×2（进口轴承交期延误、钢材盘点差异）
- 工艺问题 ×2（曲轴淬火变形、SMT回流焊虚焊）
- 生产计划 ×2（紧急插单排产、保养计划冲突）
- 环境监测 ×2（VOCs排放超标、冷却水藻类滋生）

## 许可证

MIT
