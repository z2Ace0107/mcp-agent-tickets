# AGENTS.md — LineMind

> Claude 会话恢复入口。`/clear` 后读此文件。

## 启动

```powershell
cd "E:\develop\claude\项目开发2\LineMind\linemind"
.venv/Scripts/Activate.ps1
streamlit run frontend/app.py
# → http://localhost:8501
```

## 项目定位

**多 Agent 协作框架**（非"工单系统"）。制造业工单是验证场景，核心是：

- Supervisor 路由 + 4 专业 Agent，工具子集划分
- 双通道混合检索（ChromaDB 向量 + FTS5 关键词 → RRF 融合）
- Python 沙箱代码执行（AST 分离 + 双引擎图表）
- 50 题自动化评测（全客观指标，零 LLM 消耗）

## 架构

```
用户输入 → supervisor_node(分类) → query|analyze|knowledge
  → tool_executor(超时/重试/熔断) → reporter → st.write_stream
```

- 5 Agent + 12 工具（JSON-RPC 2.0 stdio MCP）
- SQLite 13 表 + ChromaDB 向量检索
- 50 题评测集，路由 90%，工具 Jaccard 评分

## 开发流程

### 日常迭代
1. 改代码
2. 重启 Streamlit（见启动命令）
3. 浏览器手动测试关键路径
4. 必要时跑评测：`python eval/judge.py -n 10 --seed 42`

### 发版前
1. 跑全量评测：`python eval/judge.py -n 50 -o eval/report.json`
2. 改了 RAG 就跑：`python eval/bench_rag.py`
3. 更新 CHANGELOG.md
4. `git tag vX.Y.Z`
5. 提交推送

## 关键文件

| 文件 | 职责 |
|------|------|
| `backend/graph.py` | LangGraph 状态图 + 流式输出 + 工具执行器 |
| `backend/tools.py` | 12 工具实现 + execute_python 沙箱 |
| `backend/prompts.py` | 所有 Agent system prompt |
| `backend/rag.py` | 双通道检索（向量+FTS5→RRF） |
| `backend/database.py` | SQLite CRUD + 种子数据 |
| `backend/nodes/*.py` | 5 Agent 节点实现 |
| `frontend/app.py` | Streamlit 流式 UI |
| `eval/judge.py` | 自动化评测（全客观，零 token） |
| `eval/bench_rag.py` | RAG 消融对比评测 |

## 环境变量

```
DEEPSEEK_API_KEY=sk-xxx
BAIDU_API_KEY=bce-v3/ALTAK-xxx
EMBEDDING_API_KEY=sk-xxx     # 阿里百炼
```

## 文档索引

| 文档 | 内容 |
|------|------|
| [README.md](README.md) | 项目介绍、架构图、能力矩阵 |
| [CHANGELOG.md](CHANGELOG.md) | 版本演进记录 |
| [OPTIMIZE.md](OPTIMIZE.md) | 全面优化计划（删死代码/补测试/重构/飞书） |
| [HANDOFF.md](HANDOFF.md) | 旧版交接文档（部分过时） |

## 当前状态

```
v4.1 P1 ✅ → P2 部分完成 → v5.0 评测重构中
```

**分支**: `master` | **最新 tag**: `v4.1.0` | **未推送提交**: 3
