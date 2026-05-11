# -*- coding: utf-8 -*-
"""SQLite 数据库 — 工单持久化与CRUD操作"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from backend.config import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)

# ============================================================
# 数据库初始化
# ============================================================

def get_connection() -> sqlite3.Connection:
    """获取数据库连接（每次新建，线程安全）。"""
    db_path = get_settings().DATABASE_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 支持字典式访问
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    """初始化数据库：建表 + 首次空库时自动填充种子数据。

    Args:
        db_path: 数据库路径，为 None 时使用配置中的路径。
    """
    if db_path:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT '待处理',
                priority TEXT NOT NULL DEFAULT '中',
                assignee TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                description TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ticket_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                pinned INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                steps TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );
        """)
        # 兼容旧数据库：添加 pinned 列（如果不存在）
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # 列已存在
        conn.commit()

        # 空库时填入种子数据
        count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        if count == 0:
            _seed_tickets(conn)
            logger.info("数据库初始化完成，已填入 17 条种子工单")
        else:
            logger.info(f"数据库已存在 {count} 条工单，跳过种子数据")
    finally:
        conn.close()


def _seed_tickets(conn: sqlite3.Connection) -> None:
    """填入 20 条真实工厂场景工单种子数据。"""
    tickets = [
        # ===== 设备故障类 =====
        ("WO-20260428-001", "CNC加工中心主轴异响停机 — 3号生产线停线",
         "设备故障", "已解决", "紧急",
         "张建国", "2026-04-28",
         "设备编号：CNC-MC-003 | 型号：DMG MORI DMU 50 | 安装日期：2019-03\n"
         "故障现象：主轴转速升至8000rpm时出现尖锐异响，振动值从正常0.8mm/s飙升至4.2mm/s，"
         "设备自动触发紧急停机保护。3号生产线全线停产，影响当日计划产量280件（壳体精加工工序），"
         "预计产值损失约￥12,800/小时。\n"
         "初步判断：主轴轴承润滑系统异常或轴承磨损超限。上次保养日期2026-03-15，"
         "保养记录显示主轴轴承已运行超12000小时，接近设计寿命。\n"
         "已采取措施：维修班组已拆解主轴防护罩，待进一步诊断。"),

        ("WO-20260506-002", "注塑机温控系统失控导致批量产品报废",
         "设备故障", "处理中", "紧急",
         "张建国", "2026-05-06",
         "设备编号：IM-06 | 型号：海天MA3200 | 负责产品：新能源汽车连接器外壳\n"
         "故障描述：5月6日早班8:30起，注塑机4区（喷嘴段）温度显示从设定值235℃漂移至278℃，"
         "温控表PID调节无响应，导致连续39模（约156件）产品因材料过热分解出现黑点、脆化缺陷，"
         "全部报废。单件成本￥18.50，直接损失约￥2,886，模具需拆检确认流道内是否有碳化物残留。\n"
         "初步排查：热电偶接线端子氧化接触不良，加热圈继电器触点粘连无法断开。\n"
         "影响范围：该产品供应比亚迪汽车，日交付量1200件，目前安全库存仅够维持2天。"),

        ("WO-20260508-003", "空压机站2号机频繁跳闸 — 全厂气压不足",
         "设备故障", "待处理", "高",
         "", "2026-05-08",
         "设备编号：AC-02 | 型号：Atlas Copco GA90 | 功率：90kW\n"
         "故障现象：2号空压机连续3天出现运行中突然跳闸，复位后能重启但1-3小时后再次跳闸。"
         "跳闸时面板显示ERR-14（电机过载），但实测运行电流仅为额定值85%。"
         "1号机单独供气时管网压力只能维持5.2bar，低于产线要求的6.0bar最低标准，"
         "导致气动工具出力不足、自动装配线抓取失败率上升。\n"
         "已排查项：接触器触点正常无烧蚀、热继电器整定值正确、电机三相绕组绝缘＞50MΩ正常。"
         "怀疑变频器IGBT模块间歇性故障或电流传感器漂移。"),

        ("WO-20260420-004", "AGV搬运车导航偏差撞坏线边物料架",
         "设备故障", "已解决", "高",
         "张建国", "2026-04-20",
         "设备编号：AGV-05 | 型号：海康威视MR-Q3-300\n"
         "事故描述：4月20日14:22，AGV-05在执行成品入库任务（路线R-07）时，行至2号仓库D区"
         "转弯处激光SLAM定位突然漂移约40cm，右侧碰撞线边不锈钢物料架，导致物料架倾倒、"
         "架上的32件已检成品（变速箱端盖）散落地面，其中11件外观划伤需返工，物料架变形需更换。"
         "直接损失约￥2,400。\n"
         "根因分析：D区转弯处新安装了大型设备包装箱，造成激光雷达部分视野遮挡，"
         "同时该区域地面反光标识因叉车长期碾压磨损严重，双重因素导致定位失准。"),

        ("WO-20260501-005", "焊接机器人焊缝偏移不良率从0.3%升至5.7%",
         "设备故障", "处理中", "高",
         "李明辉", "2026-05-01",
         "设备编号：WR-02 | 型号：FANUC R-2000iC/210F | 焊接产品：车身加强板总成\n"
         "问题：近3天统计数据显示WR-02工位焊接的加强板总成焊缝偏移不良率从正常的≤0.3%"
         "急剧上升至5.7%，远超1.5%的控制上限。缺陷表现为焊缝偏离理论轨迹0.8-1.5mm，"
         "部分焊点熔深不足。\n"
         "排查进展：已排除焊丝批次问题（同批次另两台机器人正常）、夹具定位精度（经三坐标"
         "检测定位销磨损量0.02mm在公差内）。下一步需检查机器人TCP标定、减速机背隙、"
         "以及焊接电源输出电压稳定性。\n"
         "影响：若持续恶化，每日不良品将从约17件增至80+件，且有漏检流出的质量风险。"),

        # ===== 质量异常类 =====
        ("WO-20260505-006", "来料检验：批次钢材硬度偏低不合规",
         "质量异常", "待处理", "紧急",
         "", "2026-05-05",
         "供应商：武汉钢铁集团有限公司 | 采购单号：PO-2026-0418-035\n"
         "物料：40Cr调质钢棒材 Φ60×3000mm | 批次号：WG-2026-0428-B07 | 数量：2,800kg\n"
         "检验结果：抽样5件检测硬度，要求HRC 28-32，实测值分别为24.5、25.0、24.8、25.3、24.6，"
         "全部低于下限。同时抗拉强度检测值为880MPa（标准要求≥980MPa），延伸率偏高至18%。\n"
         "判定：整批次不合格，需退货或降级使用。该批次钢材原计划用于生产出口德国传动轴（订单号"
         "EXP-2026-0089），交期5月25日，若退货换料将导致交期延误至少15天，面临空运费及违约金。"
         "建议采购部与武钢紧急协调换货或从其他钢厂调货。"),

        ("WO-20260502-007", "成品抽检发现密封圈装配方向错误",
         "质量异常", "处理中", "紧急",
         "王桂芳", "2026-05-02",
         "产品：液压油缸总成 HC63-350 | 批次：20260501-02批（共计420件）\n"
         "问题描述：成品抽检20件中发现3件活塞密封圈（Y型圈）唇口方向装反，"
         "正确方向应为唇口朝向高压侧。装反后密封圈在工作压力超过12MPa时会翻转失效，"
         "导致油缸内泄、出力不足，严重时可能造成活塞杆弹出安全事故。\n"
         "溯源：该批次由装配线B班完成（5月1日夜班），经调取装配作业指导书和培训记录，"
         "发现2名新入职员工未通过密封圈装配专项考核即上岗操作。\n"
         "处置：该批次420件全部隔离，需逐件拆检确认密封圈方向，预计返工工时160小时。"
         "已通知生产部暂停B班相关工序，安排全员复训考核。"),

        ("WO-20260425-008", "电镀件盐雾试验96小时出现锈点",
         "质量异常", "已解决", "高",
         "王桂芳", "2026-04-25",
         "产品：户外设备安装支架（表面处理：镀锌+钝化）| 批次：20260415-A\n"
         "试验结果：按GB/T 10125标准进行中性盐雾试验，72小时检查无异常，"
         "96小时检查发现3件样品边缘及螺纹孔处出现点状红锈（≥5个锈点/件），"
         "不满足客户要求的120小时无红锈标准。\n"
         "根因分析：电镀线镀液分析显示光亮剂浓度偏低（正常值2.5-3.5ml/L，实测1.8ml/L），"
         "且钝化槽液pH值偏高（正常1.8-2.2，实测2.8），导致钝化膜不致密。"
         "该批次电镀时正值夜班交接班，操作工未按时补加光亮剂和调整钝化液。\n"
         "整改措施：重新调整镀液成分，该批次1100件全部重镀处理，"
         "建立镀液参数每2小时检测一次的加严管控措施，增加交接班复测流程。"),

        ("WO-20260507-009", "喷漆线产品表面颗粒物投诉 — 客户退货",
         "质量异常", "待处理", "高",
         "", "2026-05-07",
         "客户：三一重工 | 产品：挖掘机驾驶室外覆盖件（批次20260503-C，580件）\n"
         "投诉内容：客户IQC来料检验发现约30%产品漆面存在手感颗粒物，"
         "粒径0.1-0.5mm，分布不均匀，其中15件存在明显凸起颗粒（＞0.5mm），判定不合格退货。"
         "该批次已于5月5日发货，现要求我司3个工作日内回复8D改善报告并承担退货物流费用。\n"
         "初步排查可疑原因：1) 喷漆房5月3日下午更换了初效过滤棉，安装时可能密封不严；"
         "2) 当天室外PM10浓度偏高（沙尘天气），新风系统可能引入外界颗粒物；"
         "3) 烘干段链条润滑油加注过量，高温挥发后凝结在漆面。\n"
         "待办：喷漆车间全面清洁后做洁净度检测（要求万级），追溯同批次在库品质量状态。"),

        # ===== 安全隐患类 =====
        ("WO-20260503-010", "冲压车间安全光幕被短接 — 重大安全隐患",
         "安全隐患", "已解决", "紧急",
         "赵志强", "2026-05-03",
         "地点：冲压车间2号液压机（设备编号HP-02）| 发现人：安全巡检员周建国\n"
         "隐患描述：5月3日安全巡检中发现HP-02液压机操作侧安全光幕的连接器处被插入一根短接线，"
         "导致光幕保护功能完全失效，操作工可在光幕被遮挡情况下启动冲压循环。"
         "该设备吨位315T，合模速度200mm/s，若发生误入冲压区事故后果不堪设想。\n"
         "调查：经调取监控和询问当班班长，系操作工张某为提高连续冲压效率（安全光幕频繁被"
         "上下料动作触发导致设备暂停0.5秒/次），私自用导线短接了光幕信号线。\n"
         "处理：张某已停职接受安全教育和处罚；当班班长连带责任记过；全车间开展安全装置"
         "保护完整性专项排查；安全光幕接线盒增加防拆铅封；增设光幕旁路检测报警功能。"),

        ("WO-20260508-011", "化学品库有机溶剂泄漏 — 地面防渗层破损",
         "安全隐患", "待处理", "紧急",
         "", "2026-05-08",
         "地点：A3化学品仓库 2号存储区 | 涉及物料：二甲苯（20L桶×8桶）、油漆稀释剂（18L桶×12桶）\n"
         "隐患描述：5月8日仓管员例行巡查时发现2号存储区地面有刺激性气味，进一步检查发现"
         "一桶二甲苯（桶号XM-045）底部焊缝处有缓慢渗漏，地面已有约200ml积液，"
         "且该区域环氧树脂防渗地面存在龟裂缝隙（长约60cm，宽1-3mm），部分溶剂已渗入裂缝中。\n"
         "环境风险：二甲苯为易燃有毒化学品，蒸气与空气可形成爆炸性混合物，"
         "渗入地面后可能污染地下水监测井（最近监测井距仓库仅80m）。\n"
         "紧急处置：立即将泄漏桶转移至防泄漏托盘，用吸液棉清理地面积液，"
         "隔离2号存储区，挂置「禁止入内」警示牌。需联系环保检测公司对地面下方土壤和"
         "监测井水质取样检测，评估污染程度。"),

        ("WO-20260430-012", "叉车充电区通风系统故障 — 氢气积聚风险",
         "安全隐患", "已解决", "高",
         "赵志强", "2026-04-30",
         "地点：物流中心叉车充电间（建筑面积120㎡，配置防爆型轴流风机×2）\n"
         "隐患描述：4月30日早班，充电间氢气浓度探测器（HA-01）显示浓度达到1.2%LEL"
         "（正常＜0.2%LEL），触发黄色预警。排查发现一台排风机（EF-02）电机轴承卡死停转，"
         "另一台EF-01排风量不足额定值的60%（风管滤网严重堵塞）。充电间内有8台铅酸蓄电池叉车"
         "同时充电，产氢量约2.4m³/h，通风不足情况下氢气容易在屋顶积聚，"
         "达到4%LEL即可能发生燃爆。\n"
         "整改：更换EF-02电机轴承并测试正常运行，清洗EF-01风管滤网及叶轮；"
         "建立风机运行状况每日点检制度；增加氢气探测器定期校准周期为每月一次。"),

        # ===== 物料短缺类 =====
        ("WO-20260508-013", "关键原材料进口轴承交期延误 — 装配线即将停线",
         "物料短缺", "待处理", "紧急",
         "", "2026-05-08",
         "物料编码：PN-30215-INA | 名称：INA滚子轴承 SL04-5008PP | 单台用量2件\n"
         "供应商：德国舍弗勒（Schaeffler）| 采购方式：独家供应（客户指定品牌）\n"
         "现状：当前库存仅剩156件，以日均消耗28件计算，仅可维持5.6天生产。"
         "原计划5月6日到货的320件因国际空运航班延误（法兰克福机场罢工）推迟至5月14日，"
         "预计库存将在5月13日耗尽。\n"
         "影响产线：该轴承用于减速机总成装配线（日产14台，单台产值￥3.2万元），"
         "若停线每天直接产值损失约￥44.8万元。\n"
         "替代方案：德国供应商同意从新加坡亚太仓库紧急空运120件作为过渡（预计5月11日到），"
         "但单价上浮25%。需供应链总监在4小时内批复紧急采购申请。"),

        ("WO-20260428-014", "钢材库盘点差异 — 304不锈钢板账实不符",
         "物料短缺", "处理中", "高",
         "陈晓东", "2026-04-28",
         "物料：304冷轧不锈钢板 2.0×1500×3000mm | SAP编码：RM-304-2.0\n"
         "问题：月度盘点发现该物料ERP系统账面库存为1,280张，实际盘点仅1,102张，"
         "短缺178张（约12.7吨），按市价￥22,800/吨计算，库存差异金额约￥28.95万元。\n"
         "排查：正在逐笔核查4月份该物料所有出入库单据（包括生产领用、委外加工发出、"
         "样品领用、报废记录），同时调取1号钢材库4月份全部监控录像进行回溯比对。"
         "初步怀疑部分车间开具内部移库单但实物未办理系统过账，或移库过程中串号。\n"
         "待办：财务待盘点结果确认后进行库存调整，同步启动内控流程审查。"),

        # ===== 工艺问题类 =====
        ("WO-20260504-015", "热处理淬火后工件变形率超标 — 曲轴产品",
         "工艺问题", "处理中", "高",
         "刘红梅", "2026-05-04",
         "产品：六缸柴油机曲轴（锻钢42CrMo）| 工序：调质处理（淬火+高温回火）\n"
         "问题：5月份以来连续3批次（共计72件）曲轴在淬火后检测直线度，变形量＞0.5mm的"
         "比例从正常≤3%升高至18.5%（13件超差），超差件需增加校直工序，"
         "每件校直额外耗时45分钟且存在校裂报废风险（报废率约5%）。\n"
         "工艺参数排查：淬火油温正常（60±5℃）、工件入油方式正常（垂直悬挂）、"
         "加热温度曲线正常（850℃×2h）。但在调取加热炉炉温均匀性记录时发现，"
         "炉膛中区与边区的温差最大达±15℃（标准要求±8℃以内），导致工件加热不均匀。\n"
         "下一步：联系炉子厂家进行炉温均匀性检测和校正；先降低装炉量至70%以减小温差。"),

        ("WO-20260422-016", "SMT贴片线回流焊温度曲线漂移 — 虚焊率上升",
         "工艺问题", "已解决", "高",
         "刘红梅", "2026-04-22",
         "产线：SMT Line-3 | 产品：电机控制器PCB（12层板，BGA封装MCU）\n"
         "问题：4月20日起AOI检测直通率从98.5%下降至94.2%，不良品主要集中在BGA焊点"
         "虚焊和QFP引脚少锡，经X-Ray确认有微裂纹和冷焊现象。\n"
         "分析：对比4月18日和4月20日的回流焊温度曲线记录，发现恒温区（150-180℃）"
         "时间从正常的90±10秒缩短至55-65秒，峰值温度从245±3℃降至231-236℃，"
         "低于锡膏（Alpha OM-340）推荐峰值温度范围240-250℃。\n"
         "根因：回流焊炉第3温区上加热模组的热电偶断裂，导致该区实际温度比设定值低约25℃，"
         "PLC未检测到异常（热电偶开路时的默认值为设定值）。\n"
         "整改：更换热电偶并重新校准8个温区温度曲线，增加AOI抽检频次至每小时5片。"),

        # ===== 生产计划类 =====
        ("WO-20260508-017", "紧急插单：客户加急订单需调整排产计划",
         "生产计划", "待处理", "高",
         "", "2026-05-08",
         "客户：卡特彼勒（徐州）有限公司 | 订单号：CAT-2026-0512-RUSH\n"
         "需求：原计划6月15日交付的120台装载机变速箱体总成，需提前至5月25日交付60台"
         "（海运船期提前），剩余60台维持原交期不变。\n"
         "产能影响评估：5月份3条加工中心产线已满负荷排产至5月28日，当前订单（含本批）"
         "总产能需求为设计产能的108%。如接受加急，需：\n"
         "1) 5月12日至24日期间安排周末加班2天（需支付双倍工资约￥4.6万元）\n"
         "2) 将非紧急订单（WO-2026-0325-01）60件延后一周\n"
         "3) 外协加工商（徐州恒力机械）承接其中15台箱体粗加工（外协费增加￥3.2万）\n"
         "需生产总监在今天下班前确认是否接受此加急订单。"),

        ("WO-20260419-018", "月度设备保养计划与交付任务冲突",
         "生产计划", "已关闭", "中",
         "李明辉", "2026-04-19",
         "背景：按年度计划，4月25日-27日为全厂设备季度保养窗口（需全线停产2天），"
         "但销售部4月18日确认了一笔日本客户（小松制作所）的试制订单，要求4月28日前"
         "完成20件样品并发货。\n"
         "协调结果：设备保养调整为4月25日完成3条主产线保养（单日加班至22:00），"
         "4月26日-27日利用已完成保养的产线排产样品，4月26日-28日对其余设备进行保养。"
         "设备部、生产部、销售部三方已签字确认。"),

        # ===== 环境监测类 =====
        ("WO-20260507-019", "涂装车间VOCs排放浓度在线监测数据超标",
         "环境监测", "待处理", "紧急",
         "", "2026-05-07",
         "监测点：涂装车间废气排放口DA-002 | 监管标准：GB 37822-2019 表1限值\n"
         "异常记录：5月7日14:00-16:00时段，在线监测系统（CEMS）连续记录VOCs排放浓度"
         "为168-210mg/m³，超过60mg/m³的排放限值。同时非甲烷总烃（NMHC）浓度也上升至132mg/m³"
         "（限值100mg/m³）。该数据已自动上传至市生态环境局监控平台，可能触发环保执法检查。\n"
         "排查方向：可能为活性炭吸附装置（AC-02）吸附饱和，该活性炭已使用约11个月（设计更换"
         "周期12个月），近期喷漆量增加（加班赶货）导致处理负荷加大。\n"
         "紧急措施：降低喷漆线产能至60%，减少VOCs产生量；立即安排活性炭更换作业。"),

        ("WO-20260427-020", "冷却循环水系统藻类滋生 — 换热效率下降",
         "环境监测", "已解决", "中",
         "陈晓东", "2026-04-27",
         "系统：全厂闭式冷却水循环系统（保有水量80m³，冷却塔CT-01/02）\n"
         "问题：冷却塔出水温度从正常的32℃逐渐上升至38-40℃，导致冷水机组COP下降、"
         "制冷电耗增加约15%。开塔检查发现填料层有绿色藻类附着，水池底部有粘泥沉积，"
         "浊度从正常＜5NTU上升至25NTU。\n"
         "原因：4月份气温回升快（日均温28℃），阳光直射冷却塔水池促进了藻类繁殖；"
         "同时杀菌剂（异噻唑啉酮）投加量未随温度升高及时调整。\n"
         "处置：系统排水清洗、高压水枪冲洗填料、更换水池底泥；调整杀菌剂投加方案为"
         "夏季模式（浓度提高至15ppm、投加频次每周2次）；加装冷却塔遮阳网。"),
    ]

    conn.executemany(
        "INSERT INTO tickets (ticket_id, title, type, status, priority, assignee, created_at, updated_at, description) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[6], t[7]) for t in tickets],
    )
    conn.commit()
    logger.info(f"已填入 {len(tickets)} 条真实工厂场景种子工单")


# ============================================================
# 查询函数
# ============================================================

def query_tickets_db(
    ticket_type: str | None = None,
    status: str | None = None,
    date_range: str | None = None,
) -> list[dict[str, Any]]:
    """按条件筛选工单列表。"""
    conn = get_connection()
    try:
        query = "SELECT * FROM tickets WHERE 1=1"
        params: list[Any] = []

        if ticket_type:
            query += " AND type = ?"
            params.append(ticket_type)
        if status:
            query += " AND status = ?"
            params.append(status)

        rows = conn.execute(query, params).fetchall()
        result = [dict(r) for r in rows]

        # 日期范围筛选（Python 侧处理，兼容现有逻辑）
        if date_range:
            today = datetime.now().date()
            if date_range == "today":
                start, end = today, today
            elif date_range == "week":
                start, end = today - timedelta(days=7), today
            elif date_range == "month":
                start, end = today - timedelta(days=30), today
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
    finally:
        conn.close()


def analyze_tickets_db(analysis_type: str) -> dict[str, Any]:
    """对工单数据进行统计分析。"""
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]

        if analysis_type == "type_distribution":
            rows = conn.execute(
                "SELECT type, COUNT(*) as count FROM tickets GROUP BY type ORDER BY count DESC"
            ).fetchall()
            return {
                "analysis_type": "工单类型分布",
                "total": total,
                "data": [
                    {"type": r["type"], "count": r["count"],
                     "percentage": f"{r['count'] / total * 100:.1f}%"}
                    for r in rows
                ],
            }

        elif analysis_type == "status_distribution":
            rows = conn.execute(
                "SELECT status, COUNT(*) as count FROM tickets GROUP BY status ORDER BY count DESC"
            ).fetchall()
            return {
                "analysis_type": "工单状态分布",
                "total": total,
                "data": [
                    {"status": r["status"], "count": r["count"],
                     "percentage": f"{r['count'] / total * 100:.1f}%"}
                    for r in rows
                ],
            }

        elif analysis_type == "priority_distribution":
            order = ["高", "中", "低"]
            data = []
            for p in order:
                count = conn.execute(
                    "SELECT COUNT(*) FROM tickets WHERE priority = ?", (p,)
                ).fetchone()[0]
                data.append({
                    "priority": p, "count": count,
                    "percentage": f"{count / total * 100:.1f}%" if total else "0%",
                })
            return {"analysis_type": "工单优先级分布", "total": total, "data": data}

        elif analysis_type == "trend":
            rows = conn.execute(
                "SELECT created_at, COUNT(*) as count FROM tickets GROUP BY created_at ORDER BY created_at"
            ).fetchall()
            return {
                "analysis_type": "每日新增工单趋势",
                "total": total,
                "data": [{"date": r["created_at"], "count": r["count"]} for r in rows],
            }

        elif analysis_type == "summary":
            return {
                "analysis_type": "工单综合汇总",
                "total": total,
                "type_distribution": analyze_tickets_db("type_distribution")["data"],
                "status_distribution": analyze_tickets_db("status_distribution")["data"],
                "priority_distribution": analyze_tickets_db("priority_distribution")["data"],
                "trend": analyze_tickets_db("trend")["data"],
            }

        else:
            return {
                "error": f"不支持的分析类型: {analysis_type}",
                "supported_types": [
                    "type_distribution", "status_distribution",
                    "priority_distribution", "trend", "summary",
                ],
            }
    finally:
        conn.close()


# ============================================================
# 写操作函数
# ============================================================

def update_ticket_status_db(ticket_id: str, new_status: str) -> dict[str, Any]:
    """更新工单状态。"""
    valid_statuses = ["待处理", "处理中", "已解决", "已关闭"]
    if new_status not in valid_statuses:
        return {"error": f"无效状态: {new_status}，可选值: {', '.join(valid_statuses)}"}

    conn = get_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d")
        cursor = conn.execute(
            "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
            (new_status, now, ticket_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return {"error": f"工单不存在: {ticket_id}"}
        row = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        logger.info(f"工单 {ticket_id} 状态更新为 {new_status}")
        return dict(row)
    finally:
        conn.close()


def assign_ticket_db(ticket_id: str, assignee: str) -> dict[str, Any]:
    """分配工单给处理人。"""
    conn = get_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d")
        cursor = conn.execute(
            "UPDATE tickets SET assignee = ?, updated_at = ? WHERE ticket_id = ?",
            (assignee, now, ticket_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return {"error": f"工单不存在: {ticket_id}"}
        row = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        logger.info(f"工单 {ticket_id} 已分配给 {assignee}")
        return dict(row)
    finally:
        conn.close()


def add_ticket_reply_db(ticket_id: str, content: str) -> dict[str, Any]:
    """为工单添加回复记录。"""
    conn = get_connection()
    try:
        # 验证工单存在
        ticket = conn.execute(
            "SELECT ticket_id FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if not ticket:
            return {"error": f"工单不存在: {ticket_id}"}

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO ticket_replies (ticket_id, content, created_at) VALUES (?, ?, ?)",
            (ticket_id, content, now),
        )
        conn.commit()
        logger.info(f"工单 {ticket_id} 新增回复")
        return {"ticket_id": ticket_id, "content": content, "created_at": now, "success": True}
    finally:
        conn.close()


def get_ticket_detail_db(ticket_id: str) -> dict[str, Any]:
    """获取工单详情（含所有回复记录）。"""
    conn = get_connection()
    try:
        ticket = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if not ticket:
            return {"error": f"工单不存在: {ticket_id}"}

        replies = conn.execute(
            "SELECT * FROM ticket_replies WHERE ticket_id = ? ORDER BY created_at",
            (ticket_id,),
        ).fetchall()

        result = dict(ticket)
        result["replies"] = [dict(r) for r in replies]
        return result
    finally:
        conn.close()


def get_solved_tickets_db() -> list[dict[str, Any]]:
    """获取所有「已解决」状态的工单（供 RAG 索引使用）。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status = '已解决'"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def recommend_tickets_db() -> dict[str, Any]:
    """智能推荐分析：紧急工单、积压预警、处理人建议、关联工单。"""
    conn = get_connection()
    try:
        all_tickets = [dict(r) for r in conn.execute("SELECT * FROM tickets").fetchall()]

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        # 紧急工单：高优 + 未分配 + 待处理/处理中
        urgent = [
            t for t in all_tickets
            if t["priority"] == "高" and t["status"] in ("待处理", "处理中") and not t["assignee"]
        ]

        # 积压预警：待处理超过7天
        stale = [
            t for t in all_tickets
            if t["status"] == "待处理" and t["created_at"] <= week_ago
        ]

        # 处理人工作量统计
        workload = {}
        for t in all_tickets:
            if t["assignee"] and t["status"] in ("待处理", "处理中"):
                workload[t["assignee"]] = workload.get(t["assignee"], 0) + 1

        # 按类型统计处理人专长建议
        type_assignee_map = {}
        for t in all_tickets:
            if t["assignee"] and t["type"] not in type_assignee_map:
                type_assignee_map[t["type"]] = t["assignee"]

        # 为紧急工单推荐处理人（优先同类型有经验者，否则工作量最轻者）
        urgent_with_recs = []
        for t in urgent:
            suggested = type_assignee_map.get(t["type"])
            if not suggested and workload:
                suggested = min(workload, key=workload.get)
            urgent_with_recs.append({
                "ticket_id": t["ticket_id"],
                "title": t["title"],
                "type": t["type"],
                "priority": t["priority"],
                "status": t["status"],
                "created_at": t["created_at"],
                "suggested_assignee": suggested or "待人工指定",
            })

        # 关联工单发现：同一类型下状态相近的工单群组
        related_groups = []
        type_groups = {}
        for t in all_tickets:
            type_groups.setdefault(t["type"], []).append(t)
        for ttype, tickets in type_groups.items():
            if len(tickets) >= 2:
                # 同类型工单中有多个待处理/处理中的
                active = [t for t in tickets if t["status"] in ("待处理", "处理中")]
                if len(active) >= 2:
                    related_groups.append({
                        "type": ttype,
                        "count": len(active),
                        "tickets": [
                            {"ticket_id": t["ticket_id"], "title": t["title"], "status": t["status"]}
                            for t in active
                        ],
                    })

        # 今日工单摘要
        today_tickets = [t for t in all_tickets if t["created_at"] == today_str]
        today_by_type = {}
        for t in today_tickets:
            today_by_type[t["type"]] = today_by_type.get(t["type"], 0) + 1

        return {
            "analysis_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tickets": len(all_tickets),
            "urgent_unassigned": {
                "count": len(urgent_with_recs),
                "tickets": urgent_with_recs,
            },
            "stale_warnings": {
                "count": len(stale),
                "tickets": [
                    {"ticket_id": t["ticket_id"], "title": t["title"], "created_at": t["created_at"]}
                    for t in stale
                ],
            },
            "workload_distribution": workload,
            "related_groups": related_groups,
            "today_summary": {
                "date": today_str,
                "new_count": len(today_tickets),
                "by_type": today_by_type,
            },
            "recommended_actions": _build_action_recommendations(
                urgent_with_recs, stale, related_groups
            ),
        }
    finally:
        conn.close()


def _build_action_recommendations(
    urgent: list, stale: list, related: list
) -> list[str]:
    """根据分析结果生成操作建议列表。"""
    actions = []
    if urgent:
        actions.append(
            f"有 {len(urgent)} 个高优先级的未分配工单，建议立即分配处理人："
            + "；".join(f"{t['ticket_id']}({t['title'][:10]}...) → {t['suggested_assignee']}" for t in urgent)
        )
    if stale:
        actions.append(
            f"有 {len(stale)} 个工单积压超过7天尚未处理，建议优先跟进："
            + "、".join(t["ticket_id"] for t in stale)
        )
    if related:
        for g in related:
            if g["count"] >= 3:
                actions.append(
                    f"{g['type']}类工单有 {g['count']} 个活跃中，建议集中批量处理"
                )
    if not actions:
        actions.append("当前工单状态良好，暂无紧急待处理事项。")
    return actions


# ============================================================
# 对话历史 CRUD
# ============================================================

def create_conversation(title: str) -> int:
    """创建新对话，返回 conversation_id。"""
    conn = get_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute(
            "INSERT INTO conversations (title, created_at, updated_at) VALUES (?, ?, ?)",
            (title, now, now),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def save_message(conversation_id: int, role: str, content: str, steps: str = "[]") -> None:
    """保存单条消息到对话。"""
    conn = get_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO conversation_messages (conversation_id, role, content, steps, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content, steps, now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        conn.commit()
    finally:
        conn.close()


def load_conversation(conversation_id: int) -> dict[str, Any] | None:
    """加载指定对话的全部消息。"""
    conn = get_connection()
    try:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            return None
        messages = conn.execute(
            "SELECT * FROM conversation_messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
        return {
            "id": conv["id"],
            "title": conv["title"],
            "created_at": conv["created_at"],
            "messages": [
                {
                    "role": m["role"],
                    "content": m["content"],
                    "time": m["created_at"],
                    "steps": json.loads(m["steps"]) if m["steps"] else [],
                }
                for m in messages
            ],
        }
    finally:
        conn.close()


def list_conversations(limit: int = 50) -> list[dict[str, Any]]:
    """列出所有对话（最新在前），含预览。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            first_msg = conn.execute(
                "SELECT content FROM conversation_messages WHERE conversation_id = ? "
                "AND role = 'user' ORDER BY id LIMIT 1",
                (r["id"],),
            ).fetchone()
            preview = first_msg["content"][:80] if first_msg else ""
            result.append({
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "preview": preview,
            })
        return result
    finally:
        conn.close()


def delete_conversation(conversation_id: int) -> None:
    """删除对话及其消息。"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        conn.commit()
    finally:
        conn.close()


def update_conversation_title(conversation_id: int, title: str) -> None:
    """更新对话标题。"""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), conversation_id),
        )
        conn.commit()
    finally:
        conn.close()


def pin_conversation(conversation_id: int) -> None:
    """置顶对话。"""
    conn = get_connection()
    try:
        conn.execute("UPDATE conversations SET pinned = 1 WHERE id = ?", (conversation_id,))
        conn.commit()
    finally:
        conn.close()


def unpin_conversation(conversation_id: int) -> None:
    """取消置顶对话。"""
    conn = get_connection()
    try:
        conn.execute("UPDATE conversations SET pinned = 0 WHERE id = ?", (conversation_id,))
        conn.commit()
    finally:
        conn.close()


def list_conversations_grouped(limit: int = 50) -> dict[str, list[dict[str, Any]]]:
    """按时间分组列出对话：置顶 / 今天 / 昨天 / 7天内 / 更早。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY pinned DESC, updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        week_ago_str = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        groups: dict[str, list[dict[str, Any]]] = {"置顶": [], "今天": [], "昨天": [], "7天内": [], "更早": []}

        for r in rows:
            updated = r["updated_at"][:10]  # 取日期部分
            preview = ""
            first_msg = conn.execute(
                "SELECT content FROM conversation_messages WHERE conversation_id = ? "
                "AND role = 'user' ORDER BY id LIMIT 1",
                (r["id"],),
            ).fetchone()
            if first_msg:
                preview = first_msg["content"][:80]

            item = {
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "pinned": bool(r["pinned"]),
                "preview": preview,
            }

            if bool(r["pinned"]):
                groups["置顶"].append(item)
            elif updated == today_str:
                groups["今天"].append(item)
            elif updated == yesterday_str:
                groups["昨天"].append(item)
            elif updated > week_ago_str:
                groups["7天内"].append(item)
            else:
                groups["更早"].append(item)

        return groups
    finally:
        conn.close()


def search_conversations(query: str) -> list[dict[str, Any]]:
    """搜索对话（匹配标题或消息内容）。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT c.* FROM conversations c "
            "INNER JOIN conversation_messages m ON c.id = m.conversation_id "
            "WHERE c.title LIKE ? OR m.content LIKE ? "
            "ORDER BY c.updated_at DESC LIMIT 20",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        result = []
        for r in rows:
            first_msg = conn.execute(
                "SELECT content FROM conversation_messages WHERE conversation_id = ? "
                "AND role = 'user' ORDER BY id LIMIT 1",
                (r["id"],),
            ).fetchone()
            preview = first_msg["content"][:80] if first_msg else ""
            result.append({
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "preview": preview,
            })
        return result
    finally:
        conn.close()
