# -*- coding: utf-8 -*-
"""Streamlit 聊天界面 — 对话交互 + ReAct 推理过程可视化"""

import asyncio
import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from backend.agent import run_agent

# ============================================================
# 页面配置
# ============================================================

st.set_page_config(
    page_title="MCP智能工单助手",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🎫 MCP智能工单助手")
st.caption("基于 ReAct Agent 的工单查询与分析系统")

# ============================================================
# 会话状态初始化
# ============================================================

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # [{"role": "user/assistant", "content": str}]

if "step_history" not in st.session_state:
    st.session_state.step_history = []  # 每次对话的 intermediate_steps 快照

# ============================================================
# 侧边栏 — ReAct 推理过程
# ============================================================

with st.sidebar:
    st.header("🧠 ReAct 推理过程")

    api_key = st.text_input(
        "DeepSeek API Key",
        type="password",
        value=os.getenv("DEEPSEEK_API_KEY", ""),
        help="输入 DeepSeek API Key，或设置环境变量 DEEPSEEK_API_KEY",
    )
    if api_key:
        os.environ["DEEPSEEK_API_KEY"] = api_key

    st.divider()

    if st.session_state.step_history:
        # 显示最近一次对话的步骤
        latest_steps = st.session_state.step_history[-1]
        if latest_steps:
            for idx, step in enumerate(latest_steps, 1):
                with st.expander(f"步骤 {idx}: {step.get('action', '思考')}", expanded=(idx == 1)):
                    st.markdown(f"**💭 Thought**\n\n{step.get('thought', '')}")
                    st.markdown(f"**🔧 Action**\n\n`{step.get('action', '')}`")
                    st.markdown(f"**📥 Action Input**\n\n```json\n{step.get('action_input', '')}\n```")
                    obs = step.get("observation", "")
                    st.markdown(f"**📤 Observation**\n\n```json\n{obs[:500]}{'...' if len(obs) > 500 else ''}\n```")
    else:
        st.info("发送消息后，Agent 的推理步骤将在此展示")

# ============================================================
# 主区域 — 聊天界面
# ============================================================

# 渲染历史消息
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入框
if prompt := st.chat_input("输入你的问题，例如：最近一周有哪些退款工单？"):
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    # 确保 API Key 已设置
    if not os.getenv("DEEPSEEK_API_KEY"):
        response_text = "⚠️ 请先在侧边栏输入 DeepSeek API Key。"
        steps = []
    else:
        with st.spinner("Agent 思考中..."):
            try:
                result = asyncio.run(
                    run_agent(
                        user_input=prompt,
                        chat_history=st.session_state.chat_history[:-1],
                    )
                )
                response_text = result["output"]
                steps = result["intermediate_steps"]
            except Exception as e:
                response_text = f"❌ Agent 执行出错：{str(e)}"
                steps = []

    # 显示助手回复
    with st.chat_message("assistant"):
        st.markdown(response_text)
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})

    # 保存步骤供侧边栏展示
    st.session_state.step_history.append(steps)

    # 仅在确实无工具调用时补充占位步骤
    if not steps and os.getenv("DEEPSEEK_API_KEY"):
        # 如果 output 仍包含 ReAct 标记，说明 Agent 解析失败，不伪装成"无需工具"
        if "Action:" not in response_text and "Thought:" not in response_text:
            st.session_state.step_history[-1] = [{
                "thought": "用户输入无需调用工具，直接回复。",
                "action": "无（Final Answer）",
                "action_input": "{}",
                "observation": response_text[:500],
            }]

    st.rerun()
