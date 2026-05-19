# HANDOFF — 会话快照

> 详细操作见 [AGENTS.md](AGENTS.md)，本文记录当前会话特定状态。

## 启动

见 [AGENTS.md](AGENTS.md) 启动命令。

## 本轮会话状态 (2026-05-19)

```
v4.1 P1 ✅ → v5.0 评测重构 ✅ → P2 部分完成
```

## 本轮改动

| 提交 | 内容 |
|------|------|
| `8c931bd` | RAG 双通道 FTS5+RRF + Plotly + priority + prompts |
| `6f97876` | Plotly 弹窗修复 + 白底深字 + thinking 框架(disabled) |
| `ed9959d` | 评测重构：全客观指标，Jaccard 替换宽松匹配 |

## Git

```
ed9959d v5.0 评测重构: 全客观指标，零 LLM 消耗
6f97876 v4.1 P1: Plotly 图表修复 + 流式 thinking 框架
8c931bd v4.1 P1: RAG双通道 + Plotly图表 + query_tickets priority + 多项打磨
```
