# -*- coding: utf-8 -*-
"""v5.0 AgentLoop 核心测试 — 验证 while(hasToolCalls) 多步执行"""
import asyncio
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import init_app
from backend.config import get_settings
from backend.graph import _create_llm, ALL_TOOLS, _execute_single_tool
from backend.agent_loop import AgentLoop


async def test_single_step():
    """A 类测试：单步直达，验证 Agent 知道何时停止。"""
    print("\n" + "=" * 60)
    print("  A 类测试：单步查询")
    print("=" * 60)

    llm = _create_llm()
    agent = AgentLoop(llm=llm, tools=ALL_TOOLS, execute_tool=_execute_single_tool, verbose=True)

    tool_count = 0
    async for event in agent.run("最近一周有哪些设备故障工单？"):
        if event["type"] == "tool_call":
            tool_count += 1
            print(f"  → 工具调用: {event['tool_name']}")
        elif event["type"] == "step":
            print(f"  → 观察: {event['observation'][:80]}")
        elif event["type"] == "done":
            print(f"  → 完成 (stop_reason={event.get('stop_reason','?')})")
            print(f"  → 工具调用次数: {tool_count}")
            print(f"  → 输出前 200 字: {event.get('output', '')[:200]}")

    assert tool_count == 1, f"单步查询应只有 1 次工具调用, 实际 {tool_count}"
    print("  [PASS] 单步测试通过")
    return True


async def test_multi_step():
    """B 类测试：多步推理 — 找工单 → 查详情 → 搜方案。"""
    print("\n" + "=" * 60)
    print("  B 类测试：多步推理")
    print("=" * 60)

    llm = _create_llm()
    agent = AgentLoop(llm=llm, tools=ALL_TOOLS, execute_tool=_execute_single_tool, verbose=True)

    tools_called = []
    iterations = 0
    async for event in agent.run(
        "找出最近一周的紧急设备故障工单，然后查一下涉及哪些设备型号，"
        "再看看这些工单里有没有历史维修方案可以借鉴"
    ):
        if event["type"] == "plan":
            print(f"  → 计划: {event.get('steps', [])}")
        elif event["type"] == "tool_call":
            tools_called.append(event["tool_name"])
            print(f"  → [{len(tools_called)}] 工具: {event['tool_name']}")
        elif event["type"] == "step":
            iterations += 1
            print(f"  → 观察: {event['observation'][:100]}")
        elif event["type"] == "done":
            print(f"  → 完成 (stop_reason={event.get('stop_reason','?')})")
            print(f"  → 总迭代: {iterations}, 总工具: {len(tools_called)}")
            print(f"  → 工具序列: {tools_called}")
            print(f"  → 输出前 300 字: {event.get('output', '')[:300]}")

    # 核心断言：多步推理至少需要 2 个工具调用
    assert len(tools_called) >= 2, (
        f"多步推理应 >= 2 个工具调用, 实际 {len(tools_called)}: {tools_called}"
    )
    print("  [PASS] 多步测试通过 (AgentLoop 正确触发了多轮工具调用)")
    return True


async def test_stop_decision():
    """测试 StopDecision：简单问候应 0 工具直接返回。"""
    print("\n" + "=" * 60)
    print("  退出判断测试：闲聊直接结束")
    print("=" * 60)

    llm = _create_llm()
    agent = AgentLoop(llm=llm, tools=ALL_TOOLS, execute_tool=_execute_single_tool, verbose=True)

    tool_count = 0
    async for event in agent.run("你好"):
        if event["type"] == "tool_call":
            tool_count += 1
        elif event["type"] == "done":
            print(f"  → 完成 (stop_reason={event.get('stop_reason','?')})")
            print(f"  → 工具调用次数: {tool_count}")

    assert tool_count == 0, f"闲聊应 0 工具调用, 实际 {tool_count}"
    print("  [PASS] 退出判断测试通过")
    return True


async def main():
    print("=" * 60)
    print("  LineMind v5.0 AgentLoop 核心测试")
    print("=" * 60)

    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY:
        print("\n[SKIP] 未设置 DEEPSEEK_API_KEY")
        return

    init_app()
    print(f"  模型: {settings.DEEPSEEK_MODEL}")

    try:
        await test_stop_decision()
        await test_single_step()
        await test_multi_step()

        print("\n" + "=" * 60)
        print("  全部核心测试通过!")
        print("  while(hasToolCalls) 循环工作正常 [PASS]")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n  [FAIL] 断言失败: {e}")
        raise
    except Exception as e:
        print(f"\n  [FAIL] 测试出错: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
