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
v3.3 ✅ → 修复(8项) ✅ → v4.0 本日进度 ✅✅✅ → 继续
        ├─ 改名 LineMind ✅         ├─ RAG P0 (进行中)
        ├─ P0 Reporter 统一 ✅      ├─ 流式输出
        ├─ 50题评测体系 ✅          ├─ README 重写
        ├─ 三版对比跑分 ✅          └─ GIF + 发布
        └─ 能力矩阵 ✅
```

### 本日已完成（本次 /clear 前）

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

### 正在做：RAG P0 — solution 字段

**当前进度**：`database.py` 已加 `solution TEXT NOT NULL DEFAULT ''` 列，但：
- INSERT 语句还没改（还是旧的 12 字段）
- 种子数据还没补 solution 文本
- `rag.py` 还没改

**下一步**：
1. 给 8 条"已解决"工单写真实 solution
2. 改 executemany 的 INSERT 和 list comprehension
3. 改 rag.py：索引 solution + 返回真实 solution
4. 重新跑 50 题评测看 search_solutions 相关题目提升

### v4.0 剩余计划

1. **RAG P0** — solution 字段补完（当前 WIP）
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
