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

## 当前状态：v4.0 开发中 (2026-05-18)

```
v3.3 ✅ → 修复(8项) ✅ → v4.0 开发 ✅✅✅✅✅ → 继续
        ├─ 改名 LineMind ✅         ├─ RAG P0 ✅
        ├─ P0 Reporter 统一 ✅      ├─ LLM-as-judge ✅
        ├─ 50题评测体系 ✅          ├─ prompt修复 ✅
        ├─ 三版对比跑分 ✅          ├─ 流式输出
        └─ 能力矩阵 ✅              ├─ README 重写
                                    └─ GIF + 发布
```

### 本轮已完成 (2026-05-18)

| 事项 | 文件 | 状态 |
|------|------|:---:|
| RAG P0: solution 字段补完 | `database.py`, `rag.py` | ✅ |
| LLM-as-judge 三项指标 | `eval/judge.py` | ✅ |
| 回答相关性 → 真正 LLM 打分 | `eval/judge.py` | ✅ |
| SQL 执行成功率 | `eval/judge.py` | ✅ |
| Self-Correction 成功率 | `eval/judge.py` | ✅ |
| 写操作守卫（读查询禁调 assign/update） | `prompts.py` | ✅ |
| Supervisor 路由边界（计数归 query） | `prompts.py` | ✅ |
| 裁判 prompt 类型感知 | `eval/judge.py` | ✅ |

### v4.0 剩余计划

1. **流式输出** — `graph.py` 已有 `run_graph_stream`，需连前端 `st.write_stream`
2. **README v4.0** — 三步法故事 + 能力矩阵 + 评测数据
3. **录 GIF** — 流式输出做完后录制
4. **Git tag v4.0.0** — 收尾发布

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

> \* v2.0/v3.2/v4.0 的"相关"是旧算术公式（非真实 LLM 评分）。v4.0+fix 的 2.7/5 是 DeepSeek 真实打分。

### 版本能力矩阵

| 能力 | v2.0 | v3.2 | v4.0 |
|------|:---:|:---:|:---:|
| 基础工单查询 | ✅ | ✅ | ✅ |
| 意图路由 | ❌ | ✅ 74% | ✅ 90% |
| SQL 复杂查询 | ❌ | ❌ | ✅ |
| Python 沙箱图表 | ❌ | ❌ | ✅ |
| Schema 探索 | ❌ | ❌ | ✅ |
| SQL 自修正 | ❌ | ❌ | ✅ |
| 安全熔断 | ❌ | ❌ | ✅ |

---

## 已知问题 & 后续方向

### 裁判相关分偏低
- chat 类 1.0：裁判 prompt 已加类型感知，但 chat 回复本身简单，LLM 仍可能打低分
- multi-hop 1.5：工具链断裂（33.3%），可能需要跨 Agent 协作架构
- 回答质量：route+tool 正确 ≠ 答案好，Reporter 输出有时给建议而非数据

### 工具选择
- action 75%（从 62.5% 涨上来了，写操作守卫起效）
- multi-hop 33.3%（架构级瓶颈，Supervisor 只路由到单个 Agent）

### Self-Correction
- 全 50 题只触发 1 次，样本不足。SQL 成功率 92.3% 本身不错

---

## 评测命令

```bash
# 快速迭代（10题，~6min）
python eval/judge.py -n 10

# 全量评测（50题，~32min）
python eval/judge.py -n 50 -o eval/report.json

# 查看报告
python -c "import json; r=json.load(open('eval/report_v4.0_final.json')); print(r['summary'])"
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

## Git

```
56c76c4 feat: RAG P0 solution字段补完 + LLM-as-judge 三项指标 + prompt修复
```
