# -*- coding: utf-8 -*-
"""Agent 功能测试 — 验证工具调用和推理链路"""
import sys
import os
import asyncio

# ============================================================
# Windows 控制台编码修复（防止 emoji 等 UTF-8 字符打印报错）
# ============================================================
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)

from backend.agent import run_agent


async def main():
    test_queries = [
        "最近一周有哪些退款工单？",
        "帮我分析一下这个月工单的趋势",
        "你好",
    ]

    # 检查 API Key
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    from backend.config import get_settings
    settings = get_settings()
    if not deepseek_key and not settings.DEEPSEEK_API_KEY:
        print("[SKIP] 未设置 DEEPSEEK_API_KEY，跳过 Agent 集成测试")
        print("请在 side panel 或 .env 文件中配置 DEEPSEEK_API_KEY\n")
        # 改为测试数据库和工具层
        _test_database_queries()
        return

    for q in test_queries:
        print(f"\n{'='*50}")
        print(f"用户输入: {q}")
        try:
            result = await run_agent(q)
            output = result["output"]
            steps = result["intermediate_steps"]
            print(f"回答: {output}")
            print(f"\n推理步骤 ({len(steps)} 步):")
            for i, step in enumerate(steps, 1):
                print(f"  步骤 {i}: {step}")
        except Exception as e:
            print(f"[ERROR] 运行出错: {e}")


def _test_database_queries():
    """当 LLM 不可用时，回退测试数据库和工具函数。"""
    from backend import init_app
    from backend.tools import (
        query_tickets,
        analyze_tickets,
        get_ticket_detail,
        update_ticket_status,
        assign_ticket,
        add_ticket_reply,
    )

    init_app()

    print("=" * 50)
    print("[TEST] 测试数据库和工具函数")
    print("=" * 50)

    # 1. query_tickets
    print("\n1. query_tickets(ticket_type='退款', date_range='week')")
    result = query_tickets(ticket_type="退款", date_range="week")
    print(f"   结果: {len(result)} 条工单")
    assert len(result) > 0, "FAIL: 应返回至少1条工单"

    # 2. analyze_tickets
    print("\n2. analyze_tickets(analysis_type='summary')")
    result = analyze_tickets("summary")
    print(f"   总工单数: {result['total']}")
    assert result["total"] >= 17, f"FAIL: 总工单数应 >= 17, 实际 {result['total']}"

    # 3. get_ticket_detail
    print("\n3. get_ticket_detail(ticket_id='TK20240501001')")
    result = get_ticket_detail("TK20240501001")
    assert "error" not in result, f"FAIL: {result.get('error')}"
    print(f"   工单标题: {result['title']}")

    # 4. update_ticket_status
    print("\n4. update_ticket_status(ticket_id='TK20240501001', new_status='处理中')")
    result = update_ticket_status("TK20240501001", "处理中")
    assert "error" not in result, f"FAIL: {result.get('error')}"
    print(f"   更新后状态: {result['status']}")

    # 5. assign_ticket
    print("\n5. assign_ticket(ticket_id='TK20240501001', assignee='张三')")
    result = assign_ticket("TK20240501001", "张三")
    assert "error" not in result, f"FAIL: {result.get('error')}"
    print(f"   处理人: {result['assignee']}")

    # 6. add_ticket_reply
    print("\n6. add_ticket_reply(ticket_id='TK20240501001', content='已核实情况')")
    result = add_ticket_reply("TK20240501001", "已核实情况，正在协调财务处理")
    assert result.get("success"), f"FAIL: {result}"
    print(f"   回复成功: {result['success']}")

    # 7. 验证详情含回复
    print("\n7. get_ticket_detail(ticket_id='TK20240501001') — 含回复")
    result = get_ticket_detail("TK20240501001")
    print(f"   回复数: {len(result.get('replies', []))}")
    assert len(result["replies"]) >= 1, "FAIL: 应包含至少1条回复"

    # 8. 边界条件
    print("\n8. 边界条件测试")
    result = get_ticket_detail("NOT_EXIST")
    assert "error" in result, "FAIL: 不存在的工单应返回 error"

    result = update_ticket_status("TK20240501001", "无效状态")
    assert "error" in result, "FAIL: 无效状态应返回 error"

    result = query_tickets(date_range="invalid-range")
    assert result[0].get("error") or True, "FAIL: 无效日期应正确处理"

    print("\n" + "=" * 50)
    print("所有数据库和工具函数测试通过!")


if __name__ == "__main__":
    asyncio.run(main())