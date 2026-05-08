# -*- coding: utf-8 -*-
"""MCP工具定义与模拟工单数据"""

from datetime import datetime, timedelta
from typing import Any

# ============================================================
# 模拟工单数据（15条，涵盖多种类型、状态、优先级）
# ============================================================

_MOCK_TICKETS: list[dict[str, Any]] = [
    {
        "ticket_id": "TK20240501001",
        "title": "订单#ORD-8821 退款未到账",
        "type": "退款",
        "status": "处理中",
        "priority": "高",
        "created_at": "2026-04-28",
        "description": "用户于4月25日申请退款，系统显示已退款但用户支付宝未收到款项，已超过3个工作日。",
    },
    {
        "ticket_id": "TK20240501002",
        "title": "APP在iOS 18下闪退",
        "type": "技术",
        "status": "待处理",
        "priority": "高",
        "created_at": "2026-05-06",
        "description": "用户反馈升级iOS 18后，打开APP首页即闪退，已尝试重装无效。设备型号iPhone 16 Pro。",
    },
    {
        "ticket_id": "TK20240501003",
        "title": "会员自动续费扣款疑问",
        "type": "咨询",
        "status": "已解决",
        "priority": "低",
        "created_at": "2026-04-15",
        "description": "用户咨询会员自动续费规则，表示未收到续费提醒就扣了款，要求解释扣款逻辑。",
    },
    {
        "ticket_id": "TK20240501004",
        "title": "客服态度恶劣投诉",
        "type": "投诉",
        "status": "处理中",
        "priority": "高",
        "created_at": "2026-05-03",
        "description": "用户投诉5月2日电话客服过程中，客服人员言语不当、态度敷衍，要求公司给出处理结果。",
    },
    {
        "ticket_id": "TK20240501005",
        "title": "商品质量问题要求退货",
        "type": "退款",
        "status": "待处理",
        "priority": "中",
        "created_at": "2026-05-05",
        "description": "用户收到商品后发现明显划痕，拍照上传凭证，要求全额退货退款并承担运费。",
    },
    {
        "ticket_id": "TK20240501006",
        "title": "账号无法登录",
        "type": "技术",
        "status": "已解决",
        "priority": "中",
        "created_at": "2026-04-20",
        "description": "用户反馈使用手机验证码登录时一直提示验证码错误，经排查为短信通道延迟导致。",
    },
    {
        "ticket_id": "TK20240501007",
        "title": "订单物流信息长时间未更新",
        "type": "咨询",
        "status": "处理中",
        "priority": "低",
        "created_at": "2026-05-01",
        "description": "用户订单#ORD-9012显示已发货但物流停留在揽收阶段超过5天，咨询是否丢件。",
    },
    {
        "ticket_id": "TK20240501008",
        "title": "发票抬头开错需重开",
        "type": "咨询",
        "status": "已关闭",
        "priority": "低",
        "created_at": "2026-04-10",
        "description": "用户企业发票抬头税号填写错误，已指导用户在APP内申请红冲并重新开具。",
    },
    {
        "ticket_id": "TK20240501009",
        "title": "双十一优惠券未到账",
        "type": "投诉",
        "status": "待处理",
        "priority": "中",
        "created_at": "2026-05-07",
        "description": "用户参与平台活动领取的满200减50优惠券未在卡包中显示，要求补发。",
    },
    {
        "ticket_id": "TK20240501010",
        "title": "支付成功但订单未生成",
        "type": "技术",
        "status": "处理中",
        "priority": "高",
        "created_at": "2026-05-07",
        "description": "用户银行已扣款但系统未生成订单，涉及金额￥599.00，需紧急核查支付回调日志。",
    },
    {
        "ticket_id": "TK20240501011",
        "title": "批量退款申请（活动取消）",
        "type": "退款",
        "status": "待处理",
        "priority": "高",
        "created_at": "2026-05-08",
        "description": "因供应商原因活动取消，涉及120个订单需批量退款，总金额￥23,800.00，需紧急处理。",
    },
    {
        "ticket_id": "TK20240501012",
        "title": "积分兑换商品未发货",
        "type": "投诉",
        "status": "处理中",
        "priority": "中",
        "created_at": "2026-04-25",
        "description": "用户使用5000积分兑换的蓝牙耳机超过10天未发货，多次催促无果。",
    },
    {
        "ticket_id": "TK20240501013",
        "title": "APP页面加载缓慢",
        "type": "技术",
        "status": "已解决",
        "priority": "中",
        "created_at": "2026-04-18",
        "description": "用户反馈商品列表页加载超过10秒，经查为CDN节点故障已恢复。",
    },
    {
        "ticket_id": "TK20240501014",
        "title": "退款金额与订单金额不符",
        "type": "退款",
        "status": "已解决",
        "priority": "中",
        "created_at": "2026-04-22",
        "description": "用户订单金额￥299.00，实际退款仅收到￥269.00，差额￥30为未退还的运费。已解释平台规则后用户接受。",
    },
    {
        "ticket_id": "TK20240501015",
        "title": "账户余额异常扣减",
        "type": "技术",
        "status": "处理中",
        "priority": "高",
        "created_at": "2026-05-08",
        "description": "用户账户余额无故减少￥150.00，无对应消费记录，需排查账务系统日志。",
    },
    {
        "ticket_id": "TK20240501016",
        "title": "新功能咨询：如何开通商家入驻",
        "type": "咨询",
        "status": "已关闭",
        "priority": "低",
        "created_at": "2026-04-12",
        "description": "用户想了解商家入驻流程和资质要求，已发送入驻指南PDF至用户邮箱。",
    },
    {
        "ticket_id": "TK20240501017",
        "title": "大促期间价格保护申请",
        "type": "退款",
        "status": "待处理",
        "priority": "低",
        "created_at": "2026-05-04",
        "description": "用户购买后48小时内商品降价￥80，申请价格保护退差价，订单号#ORD-9156。",
    },
]


# ============================================================
# 工具函数
# ============================================================

def query_tickets(
    ticket_type: str | None = None,
    status: str | None = None,
    date_range: str | None = None,
) -> list[dict[str, Any]]:
    """按条件筛选工单列表。

    Args:
        ticket_type: 工单类型，可选值：退款/技术/咨询/投诉。为None则不筛选类型。
        status: 工单状态，可选值：待处理/处理中/已解决/已关闭。为None则不筛选状态。
        date_range: 日期范围，可选格式：
            - "today" — 当天
            - "week" — 近7天
            - "month" — 近30天
            - "YYYY-MM-DD,YYYY-MM-DD" — 自定义范围
            为None则不限日期。

    Returns:
        匹配条件的工单列表，每条工单为包含完整字段的字典。
    """
    result = list(_MOCK_TICKETS)
    today = datetime.now().date()

    # 按类型筛选
    if ticket_type:
        result = [t for t in result if t["type"] == ticket_type]

    # 按状态筛选
    if status:
        result = [t for t in result if t["status"] == status]

    # 按日期范围筛选
    if date_range:
        if date_range == "today":
            start = today
            end = today
        elif date_range == "week":
            start = today - timedelta(days=7)
            end = today
        elif date_range == "month":
            start = today - timedelta(days=30)
            end = today
        elif "," in date_range:
            try:
                parts = date_range.split(",")
                start = datetime.strptime(parts[0].strip(), "%Y-%m-%d").date()
                end = datetime.strptime(parts[1].strip(), "%Y-%m-%d").date()
            except ValueError:
                return [{"error": f"日期格式无效: {date_range}，请使用 YYYY-MM-DD,YYYY-MM-DD 格式"}]
        else:
            return [{"error": f"不支持的日期范围: {date_range}，支持 today/week/month/自定义范围"}]

        result = [
            t for t in result
            if start <= datetime.strptime(t["created_at"], "%Y-%m-%d").date() <= end
        ]

    return result


def analyze_tickets(analysis_type: str) -> dict[str, Any]:
    """对工单数据进行统计分析。

    Args:
        analysis_type: 分析类型，可选值：
            - "type_distribution" — 按工单类型统计数量和占比
            - "status_distribution" — 按工单状态统计数量
            - "priority_distribution" — 按优先级统计数量
            - "trend" — 按日期统计每日新增工单趋势
            - "summary" — 全部维度的汇总统计

    Returns:
        统计结果字典，具体结构取决于 analysis_type。
    """
    tickets = _MOCK_TICKETS
    total = len(tickets)

    if analysis_type == "type_distribution":
        type_counts: dict[str, int] = {}
        for t in tickets:
            tp = t["type"]
            type_counts[tp] = type_counts.get(tp, 0) + 1
        return {
            "analysis_type": "工单类型分布",
            "total": total,
            "data": [
                {"type": k, "count": v, "percentage": f"{v / total * 100:.1f}%"}
                for k, v in sorted(type_counts.items(), key=lambda x: -x[1])
            ],
        }

    elif analysis_type == "status_distribution":
        status_counts: dict[str, int] = {}
        for t in tickets:
            st = t["status"]
            status_counts[st] = status_counts.get(st, 0) + 1
        return {
            "analysis_type": "工单状态分布",
            "total": total,
            "data": [
                {"status": k, "count": v, "percentage": f"{v / total * 100:.1f}%"}
                for k, v in sorted(status_counts.items(), key=lambda x: -x[1])
            ],
        }

    elif analysis_type == "priority_distribution":
        priority_counts: dict[str, int] = {}
        for t in tickets:
            pr = t["priority"]
            priority_counts[pr] = priority_counts.get(pr, 0) + 1
        order = ["高", "中", "低"]
        return {
            "analysis_type": "工单优先级分布",
            "total": total,
            "data": [
                {"priority": p, "count": priority_counts.get(p, 0),
                 "percentage": f"{priority_counts.get(p, 0) / total * 100:.1f}%"}
                for p in order
            ],
        }

    elif analysis_type == "trend":
        date_counts: dict[str, int] = {}
        for t in tickets:
            d = t["created_at"]
            date_counts[d] = date_counts.get(d, 0) + 1
        return {
            "analysis_type": "每日新增工单趋势",
            "total": total,
            "data": [
                {"date": d, "count": c}
                for d, c in sorted(date_counts.items())
            ],
        }

    elif analysis_type == "summary":
        # 汇总：调用各维度统计
        type_dist = analyze_tickets("type_distribution")
        status_dist = analyze_tickets("status_distribution")
        priority_dist = analyze_tickets("priority_distribution")
        trend = analyze_tickets("trend")
        return {
            "analysis_type": "工单综合汇总",
            "total": total,
            "type_distribution": type_dist["data"],
            "status_distribution": status_dist["data"],
            "priority_distribution": priority_dist["data"],
            "trend": trend["data"],
        }

    else:
        return {
            "error": f"不支持的分析类型: {analysis_type}",
            "supported_types": [
                "type_distribution",
                "status_distribution",
                "priority_distribution",
                "trend",
                "summary",
            ],
        }
