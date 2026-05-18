# HANDOFF — LineMind 项目交接

> `/clear` 后读此文件即可恢复全部上下文。

## 启动

```powershell
cd "E:\develop\claude\项目开发2\LineMind\linemind"
& e:\develop\claude\.venv\Scripts\Activate.ps1
rm data/tickets.db -ErrorAction SilentlyContinue   # 首次或重置
streamlit run frontend/app.py
# → http://localhost:8501
```

## 当前状态：v4.0 开发中 (2026-05-17)

```
v3.3 ✅ → 修复(8项) ✅ → v4.0 本日进度 ✅✅✅✅ → 继续
        ├─ 改名 LineMind ✅         ├─ RAG P0 ✅ (solution 字段)
        ├─ P0 Reporter 统一 ✅      ├─ 流式输出
        ├─ 50题评测体系 ✅          ├─ README 重写
        ├─ 三版对比跑分 ✅          └─ GIF + 发布
        └─ 能力矩阵 ✅
```

### 本日已完成

| 事项 | 状态 |
|------|:---:|
| 项目改名 LineMind（文件夹+代码+文档）| ✅ |
| P0 Reporter 架构统一（走 tool_executor_node，消除 3 次崩溃）| ✅ |
| 50 题评测集（eval/test_queries.json）| ✅ |
| LLM-as-a-judge 裁判脚本（eval/judge.py）| ✅ |
| v2.0 / v3.2 / v4.0 三版对比跑分 | ✅ |
| 版本能力矩阵 | ✅ |
| AGENTS.md / HANDOFF.md 更新 | ✅ |
| 文档清理（删 3 个过期 doc） | ✅ |
| **RAG P0 — solution 字段补完** | ✅ |

### RAG P0 完成详情

- 8 条"已解决"工单全部写了 50-80 字真实处理方案
- 27 条种子工单 tuple 加 `solution` 字段，2 处 INSERT 改为 13 列
- `rag.py` index_solved_tickets 索引 solution 文本，search_solutions 返回真实 solution
- 50 题评测重新跑分：**路由 92% (+4%) | 工具 78% (+2%) | 相关 4.3/5**

### v4.0 剩余计划

1. ~~RAG P0~~ — solution 字段补完 ✅
2. **流式输出** — graph.astream 已写好在 graph.py，需连前端 st.write_stream
3. **README v4.0** — 三步法故事 + 能力矩阵 + 评测数据
4. **录 GIF** — 流式输出做完后录制
5. **Git tag v4.0.0** — 收尾发布

## 评测数据速查

### 版本能力矩阵

| 能力 | v2.0 | v3.2 | v4.0 |
|------|:---:|:---:|:---:|
| 基础工单查询 | ✅ | ✅ | ✅ |
| 意图路由 | ❌ | ✅ 74% | ✅ 88% |
| SQL 复杂查询 | ❌ | ❌ | ✅ |
| Python 沙箱图表 | ❌ | ❌ | ✅ |
| Schema 探索 | ❌ | ❌ | ✅ |
| SQL 自修正 | ❌ | ❌ | ✅ |
| 安全熔断 | ❌ | ❌ | ✅ |

v4.0 相比 v3.2 多 5 个 ✅，相比 v2.0 多 10 个 ✅。

### 评测结果速查

```
v2.0: 路由 N/A | 工具 80% | 相关 4.6 | 9 工具
v3.2: 路由 74% | 工具 82% | 相关 3.9 | 9 工具
v4.0: 路由 88% | 工具 76% | 相关 4.4 | 12 工具 (+3)
v4.0+sol: 路由 92% | 工具 78% | 相关 4.3 | 真实 solution 检索
```

## 文档结构

```
E:\develop\claude\项目开发2\LineMind\
├── AGENTS.md              ← 主线开发文档
└── linemind/              ← git repo
    ├── HANDOFF.md         ← 本文件
    ├── README.md          ← 待 v4.0 重写
    ├── eval/              ← 评测脚本 + 3 份对比报告
    └── ...
```

## 环境变量

```
DEEPSEEK_API_KEY=sk-xxx
BAIDU_API_KEY=bce-v3/ALTAK-xxx
EMBEDDING_API_KEY=sk-xxx     # 阿里百炼
```

## 架构

```
Supervisor(路由) → {Query(6) | Analyze(3) | Knowledge(3)} → Reporter
    ↑         tool_executor ← Self-Correction         │
    └──────────────────────────────────────────────────┘
```
13 张表（tickets 含 solution 列）| 5 Agent | 12 MCP 工具
