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

## 当前状态：v4.0 实习优化 (2026-05-18)

```
v3.3 ✅ → 修复(8项) ✅ → v4.0 开发 ✅✅✅✅✅ → P0 瘦身 → P1 打磨 → 发布
```

**目标：核心扎实、有亮点、不贪多。** 面向实习岗位，展示架构能力 + 工程化思维 + 数据驱动迭代。

### 本轮已完成

| 事项 | 文件 | 状态 |
|------|------|:---:|
| RAG P0: solution 字段补完 | `database.py`, `rag.py` | ✅ |
| LLM-as-judge 三项指标 | `eval/judge.py` | ✅ |
| 写操作守卫 | `prompts.py` | ✅ |
| Supervisor 路由边界 | `prompts.py` | ✅ |
| 裁判 prompt 类型感知 | `eval/judge.py` | ✅ |
| **流式输出** | `graph.py`, `app.py`, `agent.py`, 5 nodes | ✅ |

### P0 — 做减法（今天）

| # | 事项 | 文件 | 说明 |
|---|------|------|------|
| 1 | **砍 Self-Correction** | `graph.py`, `judge.py` | 50 题触发 1 次，性价比为零 |
| 2 | **Reporter 数据优先** | `prompts.py` | 数据占 80%，建议 1-2 句 |
| 3 | **Chat 评分豁免** | `eval/judge.py` | 规则判定替代 LLM 打分 |
| 4 | **测评分层** | `eval/judge.py` | 加 `--seed`，10 题日常 / 50 题发版 |
| 5 | **精简评测指标** | `eval/judge.py` | 只留路由+工具+崩溃率 |

### P1 — 打磨（明天）

| # | 事项 | 说明 |
|---|------|------|
| 6 | **README v4.0** | 三步法故事 + 能力矩阵 + 评测数据 + 架构图 |
| 7 | **录 GIF** | 流式输出 + 图表生成 |
| 8 | **Git tag v4.0.0** | 收尾发布 |

---

## 评测数据速查

### v4.0+fix 全量 50 题（最新）

```
路由: 45/50 (90.0%)    工具: 40/50 (80.0%)
SQL:  12/13 (92.3%)     SC: 0/1 (0.0%)
LLM 相关: 2.7/5
耗时: 31.9min  崩溃: 0
```

### 按类别

| 类别 | 路由 | 工具 | LLM相关 |
|------|:---:|:---:|:---:|
| query (12) | 100% | 91.7% | 3.5/5 |
| knowledge (8) | 87.5% | 87.5% | 3.1/5 |
| analyze (12) | 83.3% | 83.3% | 2.9/5 |
| action (8) | 100% | 75% | 2.4/5 |
| multi-hop (6) | 66.7% | 33.3% | 1.5/5 |
| chat (4) | 100% | 100% | 1.0/5 |

### 版本演进对比

| | v2.0 | v3.2 | v4.0 | v4.0+fix |
|------|:---:|:---:|:---:|:---:|
| 路由 | N/A | 74% | 88% | **90%** |
| 工具 | 80% | 82% | 76% | **80%** |
| SQL | — | — | — | **92.3%** |
| SC | — | — | — | **0/1** |
| 相关 | 4.6* | 3.9* | 4.4* | **2.7/5** |
| 工具数 | 9 | 9 | 12 | 12 |

### 能力矩阵（面试用）

| 能力 | v2.0 | v3.2 | v4.0 |
|------|:---:|:---:|:---:|
| 基础工单查询 | ✅ | ✅ | ✅ |
| 意图路由 | ❌ | ✅ 74% | ✅ 90% |
| SQL 复杂查询 | ❌ | ❌ | ✅ |
| Python 沙箱图表 | ❌ | ❌ | ✅ |
| Schema 探索 | ❌ | ❌ | ✅ |
| 安全熔断 | ❌ | ❌ | ✅ |

---

## 架构

```
Supervisor(路由) → {Query(6) | Analyze(3) | Knowledge(3)} → Reporter
    ↑              tool_executor                          │
    └─────────────────────────────────────────────────────┘
```
13 张表（tickets 含 solution 列）| 5 Agent | 12 MCP 工具 | 流式输出

---

## 评测命令

```bash
# 日常快速迭代（10题，~4min）
python eval/judge.py -n 10 --seed 42

# 发版全量（50题，~30min）
python eval/judge.py -n 50 -o eval/report.json --seed 42
```

---

## 环境变量

```
DEEPSEEK_API_KEY=sk-xxx
BAIDU_API_KEY=bce-v3/ALTAK-xxx
EMBEDDING_API_KEY=sk-xxx     # 阿里百炼
```

## 文档结构

```
E:\develop\claude\项目开发2\LineMind\
├── AGENTS.md              ← 主线开发文档
└── linemind/              ← git repo
    ├── HANDOFF.md         ← 本文件
    ├── README.md          ← 待 v4.0 重写
    ├── eval/              ← 评测脚本 + 报告
    │   ├── judge.py
    │   ├── test_queries.json
    │   └── report_v4.0_final.json
    └── ...
```

## Git

```
56c76c4 feat: RAG P0 solution字段补完 + LLM-as-judge 三项指标 + prompt修复
```
