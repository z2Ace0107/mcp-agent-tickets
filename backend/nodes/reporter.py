# -*- coding: utf-8 -*-
"""Reporter 节点 — 聚合上游结果 + 格式化最终回复"""

from datetime import datetime

from langchain_core.messages import SystemMessage

from backend.prompts import REPORTER_PROMPT
from backend.config import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)


def _create_llm():
    from langchain_openai import ChatOpenAI
    settings = get_settings()
    return ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        extra_body={"thinking": {"type": "disabled"}},
    )


def reporter_node(state: dict) -> dict:
    """Reporter: 可调 execute_python 画图，基于累积消息生成最终回复。"""
    import json as _json
    from backend.graph import REPORTER_TOOLS, TOOL_MAP
    from langchain_core.messages import ToolMessage, AIMessage

    llm = _create_llm()
    llm_with_tools = llm.bind_tools(REPORTER_TOOLS)

    messages = state.get("messages", [])
    user_input = state.get("rewritten_query", state["user_input"])
    steps = state.get("intermediate_steps", [])

    current_date = datetime.now().strftime("%Y年%m月%d日")
    system = SystemMessage(content=REPORTER_PROMPT.format(current_date=current_date))

    if not messages:
        from langchain_core.messages import HumanMessage
        messages = [system, HumanMessage(content=user_input)]
    else:
        messages = [system] + list(messages)

    logger.info("[reporter] 生成最终回复...")
    # 最多 2 轮：生成 → 有 execute_python → 执行 → 再生成
    for _ in range(2):
        response = llm_with_tools.invoke(messages)
        if not response.tool_calls:
            return {"messages": [response], "intermediate_steps": steps}

        # 内联执行工具（execute_python）
        tool_msgs = []
        for tc in response.tool_calls:
            tool_name = tc.get("name", "")
            tool_func = TOOL_MAP.get(tool_name)
            if tool_func:
                result = tool_func.invoke(tc.get("args", {}))
                result_str = str(result)

                # 传给 LLM 的结果要精简：去掉 base64 图片数据，避免浪费 token
                llm_result = result_str
                if tool_name == "execute_python_tool":
                    try:
                        obs_data = _json.loads(result_str)
                        charts = obs_data.get("chart_images", [])
                        if charts:
                            obs_data["chart_images"] = [f"<base64 png {len(b)} chars>" for b in charts]
                            llm_result = _json.dumps(obs_data, ensure_ascii=False)
                    except (_json.JSONDecodeError, KeyError):
                        pass
                tool_msgs.append(ToolMessage(content=llm_result, tool_call_id=tc.get("id", "")))

                # 记录步骤（含完整 chart_images，供前端渲染）
                step = {
                    "action": tool_name,
                    "action_input": _json.dumps(tc.get("args", {}), ensure_ascii=False),
                    "observation": result_str[:2000],
                    "elapsed": 0,
                    "degraded": False,
                    "retries": 0,
                }
                if tool_name == "execute_python_tool":
                    try:
                        obs_data = _json.loads(result_str)
                        charts = obs_data.get("chart_images", [])
                        if charts:
                            step["chart_images"] = charts
                    except (_json.JSONDecodeError, KeyError):
                        pass
                steps.append(step)
        messages = list(messages) + [response] + tool_msgs

    # 最后一轮强制无工具
    final_llm = _create_llm()
    response = final_llm.invoke(messages)
    return {"messages": [response], "intermediate_steps": steps}
