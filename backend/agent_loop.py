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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Callable

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

    # 检查重复
    prev_calls = [h for h in state.tool_call_history if h["tool_name"] == tool_name]
    if prev_calls:
        prev_args = prev_calls[-1].get("args", {})
        current_args = state.tool_call_history[-1].get("args", {}) if state.tool_call_history else {}
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
    response: AIMessage, observations: list[Observation], state: TaskState
) -> bool:
    """多维退出判断。"""
    if not response.tool_calls:
        return True
    if state.iterations >= MAX_ITERATIONS:
        return True
    if _check_stuck(state):
        logger.info("[agent_loop] 检测到重复调用循环，强制结束")
        return True
    return False


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
    ):
        self.llm = llm
        self.tools = tools
        self._execute_tool_fn = execute_tool
        self.max_iterations = max_iterations
        self._tool_names = [t.name for t in tools]

    def _build_system_prompt(self, state: TaskState, observation_text: str) -> str:
        return AGENT_PROMPT.format(
            tools="\n".join(f"- **{n}**" for n in self._tool_names),
            goal=state.goal,
            completed=", ".join(state.completed_steps) if state.completed_steps else "（无）",
            status=state.status,
            observation=observation_text if observation_text else "（首次执行，无上轮观察）",
        )

    def _build_initial_messages(
        self, goal: str, history: list[dict[str, str]] | None
    ) -> list:
        msgs: list = []
        if history:
            for m in history[-8:]:
                role = m.get("role", "")
                content = m.get("content", "")
                if not content:
                    continue
                if role == "user":
                    msgs.append(HumanMessage(content=content))
                elif role == "assistant":
                    msgs.append(AIMessage(content=content))
        return msgs

    async def _generate_final_answer(self, messages: list) -> str:
        """调 LLM（不带工具）生成最终答案。"""
        try:
            final_messages = list(messages) + [SystemMessage(content=FINAL_ANSWER_PROMPT)]
            final_llm = self.llm.bind_tools(self.tools, tool_choice="none")
            response = await final_llm.ainvoke(final_messages)
            return response.content or ""
        except Exception as e:
            logger.error(f"生成最终答案失败: {e}")
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

        state = TaskState(goal=goal)
        messages = self._build_initial_messages(goal, history)
        observation_text = ""
        intermediate_steps: list[dict[str, Any]] = []
        _last_response: AIMessage | None = None

        yield {
            "type": "plan",
            "steps": ["理解问题", "收集数据", "分析/检索", "输出答案"],
        }

        while state.iterations < self.max_iterations:
            # ── 上下文压缩 ──────────────────────────────────
            messages = _compress_messages(messages)

            # ── Act: 调 LLM ─────────────────────────────────
            system = SystemMessage(
                content=self._build_system_prompt(state, observation_text)
            )
            llm_with_tools = self.llm.bind_tools(self.tools)
            prompt_messages = [system] + messages

            try:
                response = await llm_with_tools.ainvoke(prompt_messages)
            except Exception as e:
                logger.error(f"LLM 调用失败: {e}")
                yield {"type": "error", "message": f"LLM 调用失败: {str(e)}"}
                return

            _last_response = response

            # 流式正文
            if response.content:
                yield {"type": "token", "content": response.content}

            # ── 无工具调用 → Agent 认为完成了 ─────────────────
            if not response.tool_calls:
                state.mark_done()
                yield {
                    "type": "done",
                    "output": response.content or "",
                    "steps": intermediate_steps,
                }
                return

            # ── Act: 执行工具 ────────────────────────────────
            tool_msgs: list[ToolMessage] = []
            observations: list[Observation] = []
            tool_metas: list[dict] = []

            for tc in response.tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                tool_call_id = tc.get("id", "")

                yield {
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "args": tool_args,
                }

                result_str, meta = self._execute_tool_fn(
                    tool_name, tool_args, circuit_state
                )
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

            state.mark_step_complete(f"第{state.iterations + 1}轮: {len(response.tool_calls)}个工具")

            # ── 退出判断 ────────────────────────────────────
            if _should_stop(response, observations, state):
                final = await self._generate_final_answer(messages)
                state.mark_done()
                yield {
                    "type": "done",
                    "output": final,
                    "steps": intermediate_steps,
                }
                return

            state.iterations += 1

        # 达到最大迭代 → 强制生成最终答案
        final = await self._generate_final_answer(messages)
        state.mark_done()
        yield {
            "type": "done",
            "output": final,
            "steps": intermediate_steps,
        }
