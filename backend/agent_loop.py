# -*- coding: utf-8 -*-
"""Agent 核心循环 v5.0 — Plan → Act → Observe → Reflect

闭环 Agent 执行框架。Agent 围绕目标持续推进任务：
while(hasToolCalls) 循环 — 检测到工具调用时继续执行并回调 LLM，
而不是直接结束。

集成方式：
- graph.py 的 agent_node 调用 AgentLoop.run() 迭代事件
- AgentLoop 内部自循环，不依赖 LangGraph 的路由
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Callable

from backend.database import save_agent_trace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from backend.config import get_settings
from backend.logger import get_logger
from backend.prompts import AGENT_PROMPT, FINAL_ANSWER_PROMPT

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════

MAX_ITERATIONS = 8
CONTEXT_BUDGET = 12000  # 字符，超过则触发压缩
KEEP_RECENT = 6  # 压缩时保留最近 N 条消息原文
MAX_HISTORY_MSGS = 6  # 历史对话保留条数
HISTORY_COMPRESS_THRESHOLD = 600  # assistant 回复超过此字符数触发截取
HISTORY_KEEP_CHARS = 300  # 截取后保留的最小信息量
MAX_TOOLS_PER_ROUND = 2  # 单轮最多执行的工具数

TOOL_CALL_LIMITS = {
    "search_solutions_tool": 1,
    "web_search_tool": 1,
    "search_equipment_manual_tool": 2,
    "query_inspection_records_tool": 3,
    "get_ticket_detail_tool": 4,
    "analyze_tickets_tool": 2,
    "execute_python_tool": 2,
    "execute_sql_tool": 5,
}

# ═══════════════════════════════════════════════════════════════
# TaskState
# ═══════════════════════════════════════════════════════════════


@dataclass
class TaskState:
    """目标驱动的结构化状态。"""

    goal: str
    completed_steps: list[str] = field(default_factory=list)
    data_collected: dict[str, Any] = field(default_factory=dict)
    tool_call_history: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    status: str = "planning"  # planning → executing → done

    def mark_step_complete(self, description: str) -> None:
        self.completed_steps.append(description)
        self.status = "executing"

    def mark_done(self) -> None:
        self.status = "done"


# ═══════════════════════════════════════════════════════════════
# Observation
# ═══════════════════════════════════════════════════════════════


@dataclass
class Observation:
    """程序化检查工具执行结果（非 LLM 猜测）。"""

    tool_name: str
    has_error: bool = False
    is_empty: bool = False
    is_duplicate: bool = False
    is_valid: bool = True
    summary: str = ""
    result_preview: str = ""

    @property
    def verdict(self) -> str:
        if self.has_error:
            return "error"
        if self.is_empty:
            return "empty"
        if self.is_duplicate:
            return "duplicate"
        return "ok"


def _observe_tool_result(
    tool_name: str, tool_result: str, state: TaskState
) -> Observation:
    """检查单个工具结果，返回结构化 Observation。"""
    obs = Observation(tool_name=tool_name)

    try:
        data = json.loads(tool_result)
    except (json.JSONDecodeError, TypeError):
        obs.has_error = True
        obs.summary = f"工具 {tool_name} 返回了无法解析的结果"
        obs.result_preview = tool_result[:200]
        obs.is_valid = False
        return obs

    # 检查 error
    if isinstance(data, dict) and data.get("error"):
        obs.has_error = True
        obs.summary = f"工具 {tool_name} 返回错误: {str(data['error'])[:150]}"
        obs.result_preview = json.dumps(data, ensure_ascii=False)[:300]
        obs.is_valid = False
        return obs

    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict) and data[0].get("error"):
        obs.has_error = True
        obs.summary = f"工具 {tool_name} 返回错误: {str(data[0]['error'])[:150]}"
        obs.result_preview = json.dumps(data, ensure_ascii=False)[:300]
        obs.is_valid = False
        return obs

    # 检查空
    if isinstance(data, list) and len(data) == 0:
        obs.is_empty = True
        obs.summary = f"工具 {tool_name} 返回空列表，没有匹配的数据"
        obs.is_valid = False
        return obs

    if isinstance(data, dict) and data.get("results") == []:
        obs.is_empty = True
        obs.summary = f"工具 {tool_name} 返回空结果，没有找到相关内容"
        obs.is_valid = False
        return obs

    # 检查重复：与上一次同工具调用比较（不含本次）
    same_tool_history = [h for h in state.tool_call_history if h["tool_name"] == tool_name]
    if len(same_tool_history) >= 2:
        prev_args = same_tool_history[-2].get("args", {})
        current_args = same_tool_history[-1].get("args", {})
        if prev_args == current_args:
            obs.is_duplicate = True
            obs.summary = f"工具 {tool_name} 用相同的参数重复调用了，结果可能没有变化"
            obs.is_valid = False
            obs.result_preview = json.dumps(data, ensure_ascii=False)[:300]
            return obs

    # 有效结果
    obs.is_valid = True
    result_count = _extract_count(data)
    obs.result_preview = json.dumps(data, ensure_ascii=False)[:500]
    obs.summary = f"工具 {tool_name} 执行成功，返回 {result_count} 条数据"
    return obs


def _extract_count(data: Any) -> int:
    """从工具结果中提取数据条目数。"""
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("results", "data", "rows", "tickets"):
            val = data.get(key)
            if isinstance(val, list):
                return len(val)
        if data.get("total"):
            return data["total"]
        if data.get("row_count"):
            return data["row_count"]
    return 0


# ═══════════════════════════════════════════════════════════════
# 循环退出判断
# ═══════════════════════════════════════════════════════════════


def _check_stuck(state: TaskState) -> bool:
    """检测是否陷入循环：连续 3 次调同一工具且结果相似。"""
    if len(state.tool_call_history) < 3:
        return False
    last_3 = state.tool_call_history[-3:]
    names = [h["tool_name"] for h in last_3]
    if len(set(names)) == 1:
        return True
    return False


def _data_sufficient(state: TaskState) -> bool:
    """判断已收集的数据是否可能足够回答用户问题。"""
    if state.iterations < 1:
        return False
    # 有工具调用历史且最后一次没有 error
    if state.tool_call_history:
        last = state.tool_call_history[-1]
        if last.get("has_error"):
            return False
    # 3 次以上有效调用通常数据够了
    valid_calls = [h for h in state.tool_call_history if not h.get("has_error")]
    return len(valid_calls) >= 5


def _should_stop(
    response: AIMessage, observations: list[Observation], state: TaskState,
    max_iterations: int = MAX_ITERATIONS, verbose: bool = False,
) -> tuple[bool, str]:
    """多维退出判断。返回 (是否退出, 原因)。

    1. LLM 没调工具 → Agent 认为任务完成
    2. 达到迭代上限 → 强制结束
    3. 陷入循环 → 连续多次同工具同参数
    4. 数据充足 → 足够有效调用可回答问题（仅在 verbose 模式记录，不强制退出）
    """
    # 条件 1：LLM 主动结束
    if not response.tool_calls:
        reason = "LLM 未调用工具，Agent 判定任务完成"
        if verbose:
            logger.info(f"[StopDecision] {reason} | 迭代: {state.iterations}")
        return True, reason

    # 条件 2：迭代上限
    if state.iterations >= max_iterations:
        reason = f"达到迭代上限 ({state.iterations}/{max_iterations})，强制结束"
        if verbose:
            logger.info(f"[StopDecision] {reason} | 工具: {[tc.get('name','') for tc in response.tool_calls]}")
        return True, reason

    # 条件 3：陷入循环
    if _check_stuck(state):
        last_3 = [h["tool_name"] for h in state.tool_call_history[-3:]]
        reason = f"陷入循环: 连续 {len(last_3)} 次调用同一工具 {last_3[0]}"
        if verbose:
            logger.info(f"[StopDecision] {reason} | 历史: {last_3}")
        return True, reason

    # 条件 4：数据充足（仅记录，不作为强制退出条件）
    if _data_sufficient(state) and verbose:
        valid = sum(1 for h in state.tool_call_history if not h.get("has_error"))
        logger.info(f"[StopDecision] 数据可能充足 ({valid} 次有效调用)，但 LLM 仍可继续")

    if verbose:
        tools = [tc.get("name", "") for tc in response.tool_calls]
        logger.info(f"[StopDecision] 继续执行 | 迭代: {state.iterations}/{max_iterations} | 本轮工具: {tools}")

    return False, "继续"


# ═══════════════════════════════════════════════════════════════
# ContextManager
# ═══════════════════════════════════════════════════════════════


def _compress_messages(messages: list, keep_recent: int = KEEP_RECENT) -> list:
    """超预算时对早期消息做 simple truncation，保留最近 N 条原文。

    使用简单裁剪而非 LLM 摘要（避免额外 token 消耗）。
    """
    total = sum(len(str(m.content)) for m in messages if hasattr(m, "content"))
    if total <= CONTEXT_BUDGET:
        return messages

    if len(messages) <= keep_recent:
        return messages

    recent = messages[-keep_recent:]
    header_text = (
        f"[上下文已压缩] 早期消息已裁剪，当前任务仍在继续。"
        f"已完成步骤: 请根据最近的工具结果继续。"
    )
    return [SystemMessage(content=header_text)] + list(recent)


def _truncate_tool_result(content: str, max_chars: int = 1500) -> str:
    """裁剪过长的工具结果，保留头尾。"""
    if len(content) <= max_chars:
        return content
    head = content[: max_chars // 2]
    tail = content[-(max_chars // 2) :]
    return f"{head}\n...[已裁剪 {len(content) - max_chars} 字符]...\n{tail}"


# ═══════════════════════════════════════════════════════════════
# AgentLoop
# ═══════════════════════════════════════════════════════════════


class AgentLoop:
    """围绕目标持续推进任务的执行循环。

    Plan → Act(LLM + Tools) → Observe(代码检查) → Reflect → ...

    用法:
        loop = AgentLoop(llm, tools, execute_tool_fn)
        async for event in loop.run("用户问题", chat_history):
            # event: {"type": "token"|"tool_call"|"tool_result"|"done", ...}
    """

    def __init__(
        self,
        llm: Any,
        tools: list[Any],
        execute_tool: Callable[[str, dict, dict], tuple[str, dict]],
        max_iterations: int = MAX_ITERATIONS,
        verbose: bool = False,
        fallback_llm: Any = None,
    ):
        self.llm = llm
        self.tools = tools
        self._execute_tool_fn = execute_tool
        self.max_iterations = max_iterations
        self.verbose = verbose
        self._tool_names = [t.name for t in tools]
        self._fallback_llm = fallback_llm
        self._llm_switched = False

    def _build_system_prompt(self, state: TaskState, observation_text: str, available_tool_names: list[str] | None = None) -> str:
        names = available_tool_names if available_tool_names is not None else self._tool_names
        return AGENT_PROMPT.format(
            tools="\n".join(f"- **{n}**" for n in names),
            max_tools_per_round=MAX_TOOLS_PER_ROUND,
            goal=state.goal,
            completed=", ".join(state.completed_steps) if state.completed_steps else "（无）",
            status=state.status,
            observation=observation_text if observation_text else "（首次执行，无上轮观察）",
        )

    def _assemble_context(
        self, goal: str, history: list[dict[str, str]] | None
    ) -> list:
        """三层消息组装（Phase 2 Context Engine）。

        Layer 1 (SystemMessage) 由 run() 中 _build_system_prompt 单独处理。
        Layer 2: History Digest — 历史对话的信息骨架，长回复截取 + 边界标记。
        Layer 3: Current Turn — 当前用户问题放在最后，确保 LLM 以当前问题为准。
        """
        msgs: list = []
        history_msgs: list = []
        if history:
            for m in history[-MAX_HISTORY_MSGS:]:
                role = m.get("role", "")
                content = m.get("content", "")
                if not content:
                    continue
                if role == "user":
                    history_msgs.append(HumanMessage(content=content))
                elif role == "assistant":
                    if len(content) > HISTORY_COMPRESS_THRESHOLD:
                        compressed = (
                            content[:HISTORY_KEEP_CHARS]
                            + f"\n\n[已压缩 {len(content)} 字符历史回复]"
                        )
                        history_msgs.append(AIMessage(content=compressed))
                    else:
                        history_msgs.append(AIMessage(content=content))
        if history_msgs:
            msgs.append(SystemMessage(content="[以下为历史对话摘要]"))
            msgs.extend(history_msgs)
        msgs.append(HumanMessage(content=goal))
        return msgs

    def _compact_tool_results(self, messages: list) -> list:
        """回合内工具结果压缩。超 CONTEXT_BUDGET 时替换最早的 ToolMessage。

        保护规则：跳过 SystemMessage，保留最近 KEEP_RECENT 条消息原文。
        递归执行直到总字符数回到预算内。
        """
        total = sum(len(str(m.content)) for m in messages if hasattr(m, "content"))
        if total <= CONTEXT_BUDGET:
            return messages

        protected_end = max(0, len(messages) - KEEP_RECENT)
        for i, msg in enumerate(messages):
            if i >= protected_end:
                break
            if isinstance(msg, ToolMessage):
                messages[i] = ToolMessage(
                    content="[工具结果已裁剪]",
                    tool_call_id=msg.tool_call_id,
                )
                return self._compact_tool_results(messages)

        return messages

    def _is_quota_error(self, error: Exception) -> bool:
        error_msg = str(error).lower()
        quota_keywords = ["429", "402", "quota", "limit", "exceeded",
                          "insufficient", "rate limit", "too many requests"]
        return any(kw in error_msg for kw in quota_keywords)

    def _switch_to_fallback(self) -> bool:
        if self._fallback_llm is not None and not self._llm_switched:
            logger.warning("Go API 额度耗尽，切换到直连 DeepSeek API")
            self.llm = self._fallback_llm
            self._llm_switched = True
            return True
        return False

    async def _generate_final_answer(self, messages: list) -> str:
        """调 LLM（不带工具）生成最终答案。失败时回退到消息中提取。"""
        try:
            final_messages = list(messages)
            final_messages = _compress_messages(final_messages, keep_recent=10)
            final_messages.append(SystemMessage(content=FINAL_ANSWER_PROMPT))
            final_llm = self.llm.bind_tools(self.tools, tool_choice="none")
            try:
                response = await final_llm.ainvoke(final_messages)
            except Exception as e:
                if self._is_quota_error(e):
                    logger.warning(f"Go API 额度耗尽 (final): {e}")
                    raise
                raise
            if response.content and response.content.strip():
                return response.content.strip()
        except Exception as e:
            logger.error(f"生成最终答案失败: {e}")

        # 回退：从最近的 AIMessage 提取内容
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                content = msg.content or ""
                if content.strip():
                    return content.strip()
        return "抱歉，生成回复时遇到问题，请重试。"

    async def run(
        self,
        goal: str,
        history: list[dict[str, str]] | None = None,
        circuit_state: dict[str, int] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """运行 Agent 循环，yield 事件字典。

        Yields:
            {"type": "plan", "steps": [...]}
            {"type": "token", "content": str}
            {"type": "tool_call", "tool_name": str, "args": dict}
            {"type": "tool_result", "tool_name": str, "meta": dict}
            {"type": "step", "action": str, "observation": str}
            {"type": "done", "output": str, "steps": [...]}
            {"type": "error", "message": str}
        """
        if circuit_state is None:
            circuit_state = {}

        trace_id = str(uuid.uuid4())[:8]
        trace_start = time.time()
        trace_steps: list[dict] = []
        trace_compressed = 0
        trace_total_msgs = 0

        state = TaskState(goal=goal)
        messages = self._assemble_context(goal, history)
        observation_text = ""
        intermediate_steps: list[dict[str, Any]] = []
        _last_response: AIMessage | None = None
        used_tools: dict[str, int] = {}

        yield {
            "type": "plan",
            "steps": ["理解问题", "收集数据", "分析/检索", "输出答案"],
            "trace_id": trace_id,
        }

        while state.iterations < self.max_iterations:
            # ── 动态工具列表：已达上限的工具从 LLM 视野中移除 ───
            available_tools = [
                t for t in self.tools
                if used_tools.get(t.name, 0) < TOOL_CALL_LIMITS.get(t.name, float("inf"))
            ]
            available_tool_names = [t.name for t in available_tools]

            # ── 上下文压缩 ──────────────────────────────────
            messages = _compress_messages(messages)

            # ── Act: 调 LLM ─────────────────────────────────
            system = SystemMessage(
                content=self._build_system_prompt(state, observation_text, available_tool_names)
            )
            llm_with_tools = self.llm.bind_tools(available_tools)
            prompt_messages = [system] + messages

            try:
                response = await llm_with_tools.ainvoke(prompt_messages)
            except Exception as e:
                if self._is_quota_error(e):
                    logger.warning(f"Go API 额度耗尽: {e}")
                    _save_trace(trace_id, goal, len(intermediate_steps), state.iterations,
                                "quota_exhausted", 0, int((time.time() - trace_start) * 1000),
                                trace_compressed, trace_total_msgs, 1, trace_steps)
                    yield {
                        "type": "quota_exhausted",
                        "message": "OpenCode Go API 额度已用完，请联系管理员切换到直连 DeepSeek API 后再试。"
                    }
                    return
                logger.error(f"LLM 调用失败: {e}")
                _save_trace(trace_id, goal, len(intermediate_steps), state.iterations,
                            "llm_error", 0, int((time.time() - trace_start) * 1000),
                            trace_compressed, trace_total_msgs, 0, trace_steps)
                yield {"type": "error", "message": f"LLM 调用失败: {str(e)}"}
                return

            _last_response = response

            # 流式正文
            if response.content:
                yield {"type": "token", "content": response.content}

            # ── 无工具调用 → Agent 认为完成了 ─────────────────
            if not response.tool_calls:
                state.mark_done()
                if self.verbose:
                    logger.info(f"[StopDecision] LLM 未调用工具，任务完成 | 迭代: {state.iterations}")
                _save_trace(trace_id, goal, len(intermediate_steps), state.iterations, "agent_finished",
                            len(response.content or ""), int((time.time() - trace_start) * 1000),
                            trace_compressed, trace_total_msgs, 0, trace_steps)
                yield {
                    "type": "done",
                    "output": response.content or "",
                    "steps": intermediate_steps,
                    "stop_reason": "agent_finished",
                    "trace_id": trace_id,
                }
                return

            # ── Act: 执行工具 ────────────────────────────────
            tool_msgs: list[ToolMessage] = []
            observations: list[Observation] = []
            tool_metas: list[dict] = []

            for i, tc in enumerate(response.tool_calls):
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                tool_call_id = tc.get("id", "")

                yield {
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "args": tool_args,
                }

                # ── 守卫 1: 每轮上限（最多 MAX_TOOLS_PER_ROUND 个）─
                if i >= MAX_TOOLS_PER_ROUND:
                    result_str = json.dumps({
                        "error": f"本轮工具调用数超限（最多{MAX_TOOLS_PER_ROUND}个/轮），此调用已跳过。请分步执行。",
                        "blocked": True,
                    }, ensure_ascii=False)
                    meta = {"elapsed": 0, "retries": 0, "degraded": False, "tool_name": tool_name, "blocked": True, "reason": "round_limit"}
                # ── 守卫 2: 工具名验证 ──────────────────────────
                elif tool_name not in available_tool_names:
                    result_str = json.dumps({
                        "error": f"工具 '{tool_name}' 不存在。可用工具: {', '.join(available_tool_names)}",
                        "blocked": True,
                    }, ensure_ascii=False)
                    meta = {"elapsed": 0, "retries": 0, "degraded": False, "tool_name": tool_name, "blocked": True, "reason": "invalid_name"}
                # ── 守卫 3: 工具调用上限（TOOL_CALL_LIMITS）────
                elif used_tools.get(tool_name, 0) >= TOOL_CALL_LIMITS.get(tool_name, float("inf")):
                    result_str = json.dumps({
                        "error": f"工具 {tool_name} 已达调用上限，禁止重复调用。请使用已有结果直接回答。",
                        "blocked": True,
                    }, ensure_ascii=False)
                    meta = {"elapsed": 0, "retries": 0, "degraded": False, "tool_name": tool_name, "blocked": True, "reason": "tool_limit"}
                # ── 正常执行 ──────────────────────────────────
                else:
                    result_str, meta = self._execute_tool_fn(
                        tool_name, tool_args, circuit_state
                    )
                    used_tools[tool_name] = used_tools.get(tool_name, 0) + 1
                truncated = _truncate_tool_result(result_str)

                tool_msgs.append(
                    ToolMessage(content=truncated, tool_call_id=tool_call_id)
                )
                tool_metas.append(meta)

                yield {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "meta": meta,
                }

                # 记录到 state
                state.tool_call_history.append({
                    "tool_name": tool_name,
                    "args": tool_args,
                    "has_error": meta.get("degraded", False) or "error" in result_str.lower()[:200],
                })

                # ── Observe: 程序化检查 ───────────────────────
                obs = _observe_tool_result(tool_name, result_str, state)
                observations.append(obs)

                step = {
                    "action": tool_name,
                    "action_input": json.dumps(tool_args, ensure_ascii=False),
                    "observation": obs.summary,
                    "elapsed": meta.get("elapsed", 0),
                }
                intermediate_steps.append(step)

                trace_steps.append({
                    "step_index": len(trace_steps),
                    "tool_name": tool_name,
                    "tool_args": json.dumps(tool_args, ensure_ascii=False),
                    "observation_verdict": obs.verdict,
                    "observation_summary": obs.summary,
                    "elapsed_ms": int(meta.get("elapsed", 0) * 1000),
                    "has_error": 1 if obs.has_error else 0,
                    "result_preview": obs.result_preview[:500] if obs.result_preview else "",
                })

                yield {"type": "step", **step}

            # ── Reflect: 构建观察文本注入下一轮 prompt ────────
            obs_lines = []
            for obs in observations:
                icon = {"ok": "[OK]", "error": "[ERROR]", "empty": "[EMPTY]", "duplicate": "[DUP]"}[obs.verdict]
                obs_lines.append(f"{icon} {obs.summary}")
            observation_text = "\n".join(obs_lines)

            # ── Reflect: 追加工具消息到对话 ──────────────────
            messages.append(response)
            messages.extend(tool_msgs)

            # ── Context Engine: 回合内工具结果压缩 ───────────
            messages = self._compact_tool_results(messages)

            state.mark_step_complete(f"第{state.iterations + 1}轮: {len(response.tool_calls)}个工具")

            # ── 退出判断 ────────────────────────────────────
            should_stop, stop_reason = _should_stop(
                response, observations, state, self.max_iterations, self.verbose
            )
            if should_stop:
                final = await self._generate_final_answer(messages)
                state.mark_done()
                _save_trace(trace_id, goal, len(intermediate_steps), state.iterations,
                            stop_reason, len(final), int((time.time() - trace_start) * 1000),
                            trace_compressed, trace_total_msgs, 0, trace_steps)
                yield {
                    "type": "done",
                    "output": final,
                    "steps": intermediate_steps,
                    "stop_reason": stop_reason,
                    "trace_id": trace_id,
                }
                return

            state.iterations += 1

            if not trace_compressed:
                total_chars = sum(len(str(m.content)) for m in messages if hasattr(m, "content"))
                if total_chars > CONTEXT_BUDGET:
                    trace_compressed = 1
            trace_total_msgs = len([m for m in messages if isinstance(m, (HumanMessage, AIMessage, ToolMessage))])

        # 达到最大迭代 → 强制生成最终答案
        final = await self._generate_final_answer(messages)
        state.mark_done()
        _save_trace(trace_id, goal, len(intermediate_steps), state.iterations,
                    f"max_iterations ({self.max_iterations})",
                    len(final), int((time.time() - trace_start) * 1000),
                    trace_compressed, trace_total_msgs, 0, trace_steps)
        yield {
            "type": "done",
            "output": final,
            "steps": intermediate_steps,
            "stop_reason": f"max_iterations ({self.max_iterations})",
            "trace_id": trace_id,
        }


def _save_trace(
    trace_id: str, question: str, total_steps: int, total_iterations: int,
    stop_reason: str, final_answer_length: int, total_latency_ms: int,
    context_compressed: int, context_total_messages: int,
    go_quota_exhausted: int, steps: list[dict],
) -> None:
    try:
        save_agent_trace(
            trace_id=trace_id, question=question, total_steps=total_steps,
            total_iterations=total_iterations, stop_reason=stop_reason,
            final_answer_length=final_answer_length,
            total_latency_ms=total_latency_ms,
            context_compressed=context_compressed,
            context_total_messages=context_total_messages,
            go_quota_exhausted=go_quota_exhausted, steps=steps,
        )
    except Exception as e:
        logger.error(f"[trace] 保存失败 {trace_id}: {e}")
