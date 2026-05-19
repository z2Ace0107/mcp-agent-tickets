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
                description TEXT NOT NULL,
                solution TEXT NOT NULL DEFAULT ''
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

            -- v3.3 星型 Schema 新增 4 表
            CREATE TABLE IF NOT EXISTS db_schema_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                data_type TEXT NOT NULL,
                is_nullable INTEGER NOT NULL DEFAULT 1,
                is_primary_key INTEGER NOT NULL DEFAULT 0,
                description TEXT DEFAULT ''
            );

            -- v3.3 星型 Schema：4 张领域表
            CREATE TABLE IF NOT EXISTS equipment (
                equipment_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                model TEXT DEFAULT '',
                install_date TEXT DEFAULT '',
                mtbf TEXT DEFAULT '',
                supplier TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS production_lines (
                line_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                product TEXT DEFAULT '',
                daily_capacity INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS materials (
                material_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                spec TEXT DEFAULT '',
                supplier TEXT DEFAULT '',
                unit_price TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS quality_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                defect_rate REAL DEFAULT 0,
                rework_hours REAL DEFAULT 0,
                FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
            );
        """)
        # 兼容旧数据库：添加 FK 列 + 新表（不影响已有数据）
        for col_stmt in [
            "ALTER TABLE tickets ADD COLUMN equipment_id TEXT",
            "ALTER TABLE tickets ADD COLUMN line_id TEXT",
            "ALTER TABLE tickets ADD COLUMN material_id TEXT",
        ]:
            try:
                conn.execute(col_stmt)
            except sqlite3.OperationalError:
                pass  # 列已存在
        conn.commit()
        # 兼容旧数据库：添加 pinned 列（如果不存在）
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # 列已存在
        conn.commit()

        # v4.0: FTS5 全文索引（RAG 双通道检索的关键词通道）
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS tickets_fts USING fts5(title, description, solution)"
        )

        # v3.3: 先种子领域表（tickets FK 依赖它们）
        _seed_equipment(conn)
        _seed_production_lines(conn)
        _seed_materials(conn)
        # 种子工单（含 FK 引用）
        _seed_tickets(conn)
        _seed_quality_metrics(conn)
        ticket_count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        logger.info(f"工单种子数据就绪，共 {ticket_count} 条")

        # Agent 系统表种子数据
        _seed_db_schema_info(conn)
        logger.info("v3.3 领域表种子数据就绪")
    finally:
        conn.close()


def _seed_tickets(conn: sqlite3.Connection) -> None:
    """填入 30+ 条真实工厂场景工单种子数据（含 FK 引用）。"""
    # 格式: (ticket_id, title, type, status, priority, assignee, created_at, description, solution, equipment_id, line_id, material_id)
    tickets = [
        # ===== 设备故障类 (5条) =====
        ("WO-20260428-001", "CNC加工中心主轴异响停机 — 3号生产线停线",
         "设备故障", "已解决", "紧急",
         "张建国", "2026-04-28",
         "设备编号：CNC-MC-003 | 型号：DMG MORI DMU 50 | 安装日期：2019-03\n"
         "故障现象：主轴转速升至8000rpm时出现尖锐异响，振动值从正常0.8mm/s飙升至4.2mm/s，"
         "设备自动触发紧急停机保护。3号生产线全线停产，影响当日计划产量280件（壳体精加工工序）。\n"
         "初步判断：主轴轴承润滑系统异常或轴承磨损超限。上次保养日期2026-03-15，"
         "保养记录显示主轴轴承已运行超12000小时，接近设计寿命。",
         "更换主轴轴承（SKF 7014 ACD/P4A），重新校准主轴动平衡至G1级，振动值恢复至0.8mm/s。"
         "建立主轴轴承运行时间台账，设定10000小时强制更换周期。3号线当日恢复生产，追回产量280件。",
         "EQP-001", "LINE-001", None),

        ("WO-20260506-002", "注塑机温控系统失控导致批量产品报废",
         "设备故障", "处理中", "紧急",
         "张建国", "2026-05-06",
         "设备编号：IM-06 | 型号：海天MA3200 | 负责产品：新能源汽车连接器外壳\n"
         "故障描述：5月6日早班8:30起，注塑机4区（喷嘴段）温度显示从设定值235℃漂移至278℃，"
         "温控表PID调节无响应，导致连续39模（约156件）产品因材料过热分解出现黑点、脆化缺陷，"
         "全部报废。单件成本￥18.50，直接损失约￥2,886。\n"
         "初步排查：热电偶接线端子氧化接触不良，加热圈继电器触点粘连无法断开。",
         "", "EQP-002", None, None),

        ("WO-20260508-003", "空压机站2号机频繁跳闸 — 全厂气压不足",
         "设备故障", "待处理", "高",
         "", "2026-05-08",
         "设备编号：AC-02 | 型号：Atlas Copco GA90 | 功率：90kW\n"
         "故障现象：2号空压机连续3天出现运行中突然跳闸，复位后能重启但1-3小时后再次跳闸。"
         "跳闸时面板显示ERR-14（电机过载），但实测运行电流仅为额定值85%。"
         "1号机单独供气时管网压力只能维持5.2bar，低于产线要求的6.0bar最低标准。\n"
         "怀疑变频器IGBT模块间歇性故障或电流传感器漂移。",
         "", "EQP-003", None, None),

        ("WO-20260420-004", "AGV搬运车导航偏差撞坏线边物料架",
         "设备故障", "已解决", "高",
         "张建国", "2026-04-20",
         "设备编号：AGV-05 | 型号：海康威视MR-Q3-300\n"
         "事故描述：4月20日14:22，AGV-05在执行成品入库任务时，行至2号仓库D区"
         "转弯处激光SLAM定位突然漂移约40cm，右侧碰撞线边不锈钢物料架，导致物料架倾倒。\n"
         "根因分析：D区转弯处新安装了大型设备包装箱，造成激光雷达部分视野遮挡，"
         "同时该区域地面反光标识因叉车长期碾压磨损严重。",
         "重新标定AGV-05激光SLAM定位参数，清除D区转弯处遮挡物并设置禁停标识。"
         "重新铺设地面反光标识，增设防碰撞二级减速区。更新AGV路径规划避让规则，转弯通道宽度下限从1.5m调整为2.0m。",
         "EQP-004", None, None),

        ("WO-20260501-005", "焊接机器人焊缝偏移不良率从0.3%升至5.7%",
         "设备故障", "处理中", "高",
         "李明辉", "2026-05-01",
         "设备编号：WR-02 | 型号：FANUC R-2000iC/210F | 焊接产品：车身加强板总成\n"
         "问题：近3天统计数据显示WR-02工位焊接的加强板总成焊缝偏移不良率从正常的≤0.3%"
         "急剧上升至5.7%，远超1.5%的控制上限。缺陷表现为焊缝偏离理论轨迹0.8-1.5mm。\n"
         "排查进展：已排除焊丝批次问题、夹具定位精度。下一步需检查机器人TCP标定、减速机背隙。",
         "", "EQP-005", None, None),

        # ===== 质量异常类 (4条) =====
        ("WO-20260505-006", "来料检验：批次钢材硬度偏低不合规",
         "质量异常", "待处理", "紧急",
         "", "2026-05-05",
         "供应商：武汉钢铁集团有限公司 | 采购单号：PO-2026-0418-035\n"
         "物料：40Cr调质钢棒材 Φ60×3000mm | 批次号：WG-2026-0428-B07 | 数量：2,800kg\n"
         "检验结果：抽样5件检测硬度，要求HRC 28-32，实测值全部低于下限。"
         "该批次钢材原计划用于生产出口德国传动轴，若退货换料将导致交期延误至少15天。",
         "", None, None, "MAT-001"),

        ("WO-20260502-007", "成品抽检发现密封圈装配方向错误",
         "质量异常", "处理中", "紧急",
         "王桂芳", "2026-05-02",
         "产品：液压油缸总成 HC63-350 | 批次：20260501-02批（共计420件）\n"
         "问题描述：成品抽检20件中发现3件活塞密封圈（Y型圈）唇口方向装反。\n"
         "溯源：该批次由装配线B班完成，发现2名新入职员工未通过密封圈装配专项考核即上岗操作。\n"
         "处置：该批次420件全部隔离，需逐件拆检确认密封圈方向，预计返工工时160小时。",
         "", None, "LINE-002", "MAT-002"),

        ("WO-20260425-008", "电镀件盐雾试验96小时出现锈点",
         "质量异常", "已解决", "高",
         "王桂芳", "2026-04-25",
         "产品：户外设备安装支架（表面处理：镀锌+钝化）| 批次：20260415-A\n"
         "试验结果：按GB/T 10125标准进行中性盐雾试验，72小时检查无异常，"
         "96小时检查发现3件样品边缘及螺纹孔处出现点状红锈，不满足客户要求的120小时无红锈标准。\n"
         "根因分析：电镀线镀液分析显示光亮剂浓度偏低，且钝化槽液pH值偏高，导致钝化膜不致密。",
         "调整电镀线光亮剂浓度至0.8-1.2ml/L工艺标准值，降低钝化槽液pH至2.0-2.5。"
         "复测盐雾试验通过120小时无红锈标准。建立镀液成分每日分析制度，编制钝化槽pH值SPC控制图。",
         None, None, None),

        ("WO-20260507-009", "喷漆线产品表面颗粒物投诉 — 客户退货",
         "质量异常", "待处理", "高",
         "", "2026-05-07",
         "客户：三一重工 | 产品：挖掘机驾驶室外覆盖件（批次20260503-C，580件）\n"
         "投诉内容：客户IQC来料检验发现约30%产品漆面存在手感颗粒物，判定不合格退货。\n"
         "初步排查可疑原因：1) 喷漆房更换初效过滤棉时安装密封不严；"
         "2) 当天室外PM10浓度偏高（沙尘天气）；3) 烘干段链条润滑油加注过量。",
         "", None, None, None),

        # ===== 安全隐患类 (3条) =====
        ("WO-20260503-010", "冲压车间安全光幕被短接 — 重大安全隐患",
         "安全隐患", "已解决", "紧急",
         "赵志强", "2026-05-03",
         "地点：冲压车间2号液压机（设备编号HP-02）| 发现人：安全巡检员周建国\n"
         "隐患描述：5月3日安全巡检中发现HP-02液压机操作侧安全光幕的连接器处被插入一根短接线，"
         "导致光幕保护功能完全失效。该设备吨位315T，合模速度200mm/s。\n"
         "处理：张某已停职接受安全教育和处罚；全车间开展安全装置保护完整性专项排查。",
         "拆除短接线恢复光幕保护功能，测试确认保护距离及响应时间均符合GB 4584标准。"
         "当事人张某停职接受72学时安全培训，考核通过后方可返岗。全车间排查27台冲压设备安全装置完整性，未发现其他违规。",
         "EQP-006", None, None),

        ("WO-20260508-011", "化学品库有机溶剂泄漏 — 地面防渗层破损",
         "安全隐患", "待处理", "紧急",
         "", "2026-05-08",
         "地点：A3化学品仓库 2号存储区 | 涉及物料：二甲苯（20L桶×8桶）、油漆稀释剂（18L桶×12桶）\n"
         "隐患描述：5月8日仓管员例行巡查时发现一桶二甲苯（桶号XM-045）底部焊缝处有缓慢渗漏，"
         "且该区域环氧树脂防渗地面存在龟裂缝隙（长约60cm）。\n"
         "紧急处置：立即将泄漏桶转移至防泄漏托盘，用吸液棉清理地面积液，隔离2号存储区。",
         "", None, None, "MAT-006"),

        ("WO-20260430-012", "叉车充电区通风系统故障 — 氢气积聚风险",
         "安全隐患", "已解决", "高",
         "赵志强", "2026-04-30",
         "地点：物流中心叉车充电间（建筑面积120㎡，配置防爆型轴流风机×2）\n"
         "隐患描述：4月30日早班，充电间氢气浓度探测器显示浓度达到1.2%LEL（正常＜0.2%LEL），"
         "触发黄色预警。排查发现一台排风机（EF-02）电机轴承卡死停转。\n"
         "整改：更换EF-02电机轴承并测试正常运行，建立风机运行状况每日点检制度。",
         "更换EF-02排风机电机轴承（SKF 6205-2Z），恢复双风机运行。氢气浓度降至0.05%LEL以下。"
         "建立《叉车充电间排风系统每日点检表》，每班次值班电工签字确认风机运行状态。",
         "EQP-009", None, None),

        # ===== 物料短缺类 (2条) =====
        ("WO-20260508-013", "关键原材料进口轴承交期延误 — 装配线即将停线",
         "物料短缺", "待处理", "紧急",
         "", "2026-05-08",
         "物料编码：PN-30215-INA | 名称：INA滚子轴承 SL04-5008PP | 单台用量2件\n"
         "供应商：德国舍弗勒（Schaeffler）| 采购方式：独家供应（客户指定品牌）\n"
         "现状：当前库存仅剩156件，以日均消耗28件计算，仅可维持5.6天生产。\n"
         "影响产线：该轴承用于减速机总成装配线（日产14台，单台产值￥3.2万元）。",
         "", None, "LINE-003", "MAT-003"),

        ("WO-20260428-014", "钢材库盘点差异 — 304不锈钢板账实不符",
         "物料短缺", "处理中", "高",
         "陈晓东", "2026-04-28",
         "物料：304冷轧不锈钢板 2.0×1500×3000mm | SAP编码：RM-304-2.0\n"
         "问题：月度盘点发现该物料ERP系统账面库存为1,280张，实际盘点仅1,102张，"
         "短缺178张（约12.7吨），按市价￥22,800/吨计算，库存差异金额约￥28.95万元。",
         "", None, None, "MAT-004"),

        # ===== 工艺问题类 (2条) =====
        ("WO-20260504-015", "热处理淬火后工件变形率超标 — 曲轴产品",
         "工艺问题", "处理中", "高",
         "刘红梅", "2026-05-04",
         "产品：六缸柴油机曲轴（锻钢42CrMo）| 工序：调质处理（淬火+高温回火）\n"
         "问题：5月份以来连续3批次（共计72件）曲轴在淬火后检测直线度，变形量＞0.5mm的"
         "比例从正常≤3%升高至18.5%。\n"
         "工艺参数排查：炉膛中区与边区的温差最大达±15℃（标准要求±8℃以内）。",
         "", None, None, "MAT-001"),

        ("WO-20260422-016", "SMT贴片线回流焊温度曲线漂移 — 虚焊率上升",
         "工艺问题", "已解决", "高",
         "刘红梅", "2026-04-22",
         "产线：SMT Line-3 | 产品：电机控制器PCB（12层板，BGA封装MCU）\n"
         "问题：4月20日起AOI检测直通率从98.5%下降至94.2%，不良品主要集中在BGA焊点虚焊和QFP引脚少锡。\n"
         "根因：回流焊炉第3温区上加热模组的热电偶断裂，导致该区实际温度比设定值低约25℃。",
         "更换回流焊炉第3温区上加热模组K型热电偶，重新校准各温区温度曲线。AOI直通率恢复至98.5%。"
         "建立每周炉温曲线实测校验制度，超出±3℃自动触发报警。",
         "EQP-007", "LINE-004", None),

        # ===== 生产计划类 (2条) =====
        ("WO-20260508-017", "紧急插单：客户加急订单需调整排产计划",
         "生产计划", "待处理", "高",
         "", "2026-05-08",
         "客户：卡特彼勒（徐州）有限公司 | 订单号：CAT-2026-0512-RUSH\n"
         "需求：原计划6月15日交付的120台装载机变速箱体总成，需提前至5月25日交付60台。\n"
         "产能影响评估：5月份3条加工中心产线已满负荷排产至5月28日，当前订单总产能需求为设计产能的108%。",
         "", None, "LINE-001", None),

        ("WO-20260419-018", "月度设备保养计划与交付任务冲突",
         "生产计划", "已关闭", "中",
         "李明辉", "2026-04-19",
         "背景：按年度计划，4月25日-27日为全厂设备季度保养窗口（需全线停产2天），"
         "但销售部4月18日确认了一笔日本客户（小松制作所）的试制订单，要求4月28日前完成20件样品并发货。\n"
         "协调结果：设备保养调整为4月25日完成3条主产线保养（单日加班至22:00），"
         "4月26日-27日利用已完成保养的产线排产样品。",
         "", None, None, None),

        # ===== 环境监测类 (2条) =====
        ("WO-20260507-019", "涂装车间VOCs排放浓度在线监测数据超标",
         "环境监测", "待处理", "紧急",
         "", "2026-05-07",
         "监测点：涂装车间废气排放口DA-002 | 监管标准：GB 37822-2019 表1限值\n"
         "异常记录：5月7日14:00-16:00时段，在线监测系统连续记录VOCs排放浓度"
         "为168-210mg/m³，超过60mg/m³的排放限值。\n"
         "紧急措施：降低喷漆线产能至60%，减少VOCs产生量；立即安排活性炭更换作业。",
         "", "EQP-010", None, None),

        ("WO-20260427-020", "冷却循环水系统藻类滋生 — 换热效率下降",
         "环境监测", "已解决", "中",
         "陈晓东", "2026-04-27",
         "系统：全厂闭式冷却水循环系统（保有水量80m³，冷却塔CT-01/02）\n"
         "问题：冷却塔出水温度从正常的32℃逐渐上升至38-40℃，导致冷水机组COP下降、"
         "制冷电耗增加约15%。\n"
         "原因：4月份气温回升快（日均温28℃），阳光直射冷却塔水池促进了藻类繁殖。",
         "投放异噻唑啉酮非氧化型杀菌灭藻剂冲击处理，48小时后置换系统循环水。"
         "在冷却塔水池上方加装遮阳棚，建立每月投加缓释型杀菌剂球的定期维护制度。冷却塔出水温度恢复至32℃。",
         None, None, None),

        # ===== v3.3 新增工单 (7条) =====
        ("WO-20260509-021", "涂装机器人3号臂喷涂不均匀 — 漆膜厚度超标",
         "设备故障", "处理中", "高",
         "张建国", "2026-05-09",
         "设备编号：PT-R03 | 型号：ABB IRB 5500 | 安装日期：2020-06\n"
         "故障现象：涂装机器人3号臂在喷涂大型覆盖件时出现漆膜厚度不均匀，"
         "膜厚偏差从正常的±5μm扩大至±18μm，导致面漆光泽度不一致。\n"
         "初步排查：机器人腕部齿轮箱背隙可能增大，需检测重复定位精度。",
         "", "EQP-010", None, None),

        ("WO-20260510-022", "外协加工件尺寸超差 — 批量退货",
         "质量异常", "待处理", "紧急",
         "", "2026-05-10",
         "外协商：徐州恒力机械 | 物料：变速箱体粗加工件 | 批次：XZ-2026-0508\n"
         "问题：IQC检验发现50件中有12件关键尺寸（轴承孔Φ120H7）超上差+0.025mm，"
         "无法进入精加工工序。该批共300件，需全检并返工或退货。\n"
         "影响：若退货将导致装配线待料停产，需紧急协调其他外协商补货。",
         "", None, None, None),

        ("WO-20260511-023", "数控磨床砂轮动平衡失效 — 加工表面振纹",
         "设备故障", "已解决", "高",
         "李明辉", "2026-05-11",
         "设备编号：CG-04 | 型号：Studer S41 | 加工产品：精密主轴\n"
         "故障现象：磨削加工后工件表面出现规律性振纹（间距约3mm），粗糙度Ra从正常0.2μm升至0.8μm。\n"
         "根因：砂轮动平衡块在高速旋转中微量位移，导致动平衡精度从G1级降为G6.3级。\n"
         "整改：重新进行砂轮动平衡校正，建立每班次动平衡点检制度。",
         "重新进行砂轮动平衡校正，精度恢复至G1级（残余不平衡量<0.5g·mm/kg）。加工件表面粗糙度恢复至Ra 0.2μm。"
         "建立每班次砂轮动平衡点检制度，使用便携式动平衡仪快速检测，超出G2.5级立即校正。",
         None, None, None),

        ("WO-20260512-024", "装配线气动扳手扭力不足 — 螺栓锁紧不合格",
         "设备故障", "待处理", "高",
         "", "2026-05-12",
         "设备：Atlas Copco 气动扭力扳手 TQ-03 | 所属空压机站 AC-02 供气\n"
         "问题：5号总装线早班巡检发现气动扳手输出扭力从标准180Nm下降至145-155Nm，"
         "导致M16螺栓锁紧力矩不足，在线扭矩监控系统连续报警12次。\n"
         "初步排查：关联空压机AC-02跳闸问题导致供气管路压力波动。",
         "", "EQP-003", None, None),

        ("WO-20260513-025", "磷化线槽液参数异常 — 磷化膜结晶粗大",
         "工艺问题", "处理中", "中",
         "刘红梅", "2026-05-13",
         "产线：磷化处理线 PL-02 | 槽液：锌系磷化液（总酸度/游离酸度/促进剂浓度）\n"
         "问题：连续2天磷化膜SEM检测显示结晶粗大（正常晶粒3-8μm，实际15-25μm），"
         "膜重从正常2.5g/m²升至4.2g/m²，可能导致后续电泳附着力下降。\n"
         "排查方向：槽液游离酸度偏高（正常0.8-1.2点，实测1.8点），需调整中和。",
         "", None, None, None),

        ("WO-20260514-026", "成品库恒温恒湿系统故障 — 精密件表面凝露",
         "环境监测", "待处理", "紧急",
         "", "2026-05-14",
         "地点：成品库2号恒温恒湿仓 | 库存：精密轴承、伺服电机等（总值约￥380万）\n"
         "问题：5月14日凌晨湿度传感器显示相对湿度从45%骤升至82%，温度波动±5℃，"
         "导致部分精密件包装内出现凝露。空调机组制冷剂泄漏，压缩机低压保护停机。\n"
         "紧急措施：转移高价值库存至备用仓，联系空调维修商紧急补漏充氟。",
         "", None, None, None),

        ("WO-20260515-027", "供应商来料包装破损率突然升高 — 运输环节排查",
         "物料短缺", "待处理", "中",
         "陈晓东", "2026-05-15",
         "供应商：鞍钢集团 | 物料：45#调质钢棒材 | 运输方式：公路货运\n"
         "问题：5月份以来连续3车次到货时发现包装木箱破损率达35%（正常≤5%），"
         "导致棒材表面划伤、端部磕碰，影响后续加工。\n"
         "排查方向：更换货运承包商后的运输加固方案是否合规，包装木箱强度是否达标。",
         "", None, None, "MAT-005"),
    ]

    conn.executemany(
        "INSERT OR IGNORE INTO tickets (ticket_id, title, type, status, priority, assignee, created_at, updated_at, description, solution, equipment_id, line_id, material_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[6], t[7], t[8], t[9], t[10], t[11]) for t in tickets],
    )
    # v3.3: 当天日期工单（动态生成，含 FK 引用）
    from datetime import datetime as dt
    today_str = dt.now().strftime("%Y-%m-%d")
    today_prefix = today_str.replace("-", "")
    today_tickets = [
        ("WO-{}-T01".format(today_prefix), "今日紧急：涂装车间VOCs排放在线监测数据超标",
         "环境监测", "待处理", "紧急",
         "", today_str,
         "监测点：涂装车间废气排放口DA-002 | 监管标准：GB 37822-2019\n"
         "异常记录：今日14:00-16:00时段，VOCs排放浓度超60mg/m³限值。\n"
         "紧急措施：降低喷漆线产能至60%，安排活性炭更换作业。",
         "", "EQP-010", None, None),
        ("WO-{}-T02".format(today_prefix), "今日新增：CNC加工中心主轴冷却系统报警",
         "设备故障", "待处理", "高",
         "", today_str,
         "设备编号：CNC-MC-007 | 型号：DMG MORI DMU 50\n"
         "故障现象：主轴冷却液温度异常升高至42℃（正常范围25-35℃），触发黄色预警。\n"
         "初步判断：冷却液循环泵流量不足或热交换器堵塞。需安排停机检修。",
         "", "EQP-008", None, None),
        ("WO-{}-T03".format(today_prefix), "今日新增：来料检验批次钢材硬度偏低",
         "质量异常", "待处理", "高",
         "", today_str,
         "供应商：鞍钢集团 | 物料：45#调质钢棒材 Φ80×3000mm | 批次号：AG-2026-0515-C02\n"
         "检验结果：抽样硬度要求HRC 22-28，实测值偏低，需技术评审决定让步接收或退货。",
         "", None, None, "MAT-005"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO tickets (ticket_id, title, type, status, priority, assignee, created_at, updated_at, description, solution, equipment_id, line_id, material_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[6], t[7], t[8], t[9], t[10], t[11]) for t in today_tickets],
    )
    conn.commit()
    logger.info(f"已填充 {len(tickets)} 条历史工单 + {len(today_tickets)} 条今日工单")


def _seed_equipment(conn: sqlite3.Connection) -> None:
    """填入设备种子数据。"""
    equipment = [
        ("EQP-001", "CNC加工中心(3号线)", "DMG MORI DMU 50", "2019-03", "12000h", "DMG MORI"),
        ("EQP-002", "注塑机(6号)", "海天MA3200", "2020-05", "8000h", "海天"),
        ("EQP-003", "空压机(2号)", "Atlas Copco GA90", "2018-10", "15000h", "Atlas Copco"),
        ("EQP-004", "AGV搬运车(5号)", "海康威视MR-Q3-300", "2021-02", "6000h", "海康威视"),
        ("EQP-005", "焊接机器人(WR-02)", "FANUC R-2000iC/210F", "2020-08", "10000h", "FANUC"),
        ("EQP-006", "液压机(2号,HP-02)", "315T四柱液压机", "2017-06", "20000h", "合肥锻压"),
        ("EQP-007", "SMT贴片线(Line-3)", "Yamaha YSM20R", "2021-06", "5000h", "Yamaha"),
        ("EQP-008", "CNC加工中心(CNC-MC-007)", "DMG MORI DMU 50", "2019-06", "11000h", "DMG MORI"),
        ("EQP-009", "排风机(EF-01/EF-02)", "防爆型轴流风机", "2019-03", "15000h", "上风高科"),
        ("EQP-010", "涂装机器人(PT-R03)/活性炭吸附(AC-02)", "ABB IRB 5500", "2020-06", "9000h", "ABB"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO equipment (equipment_id, name, model, install_date, mtbf, supplier) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        equipment,
    )
    conn.commit()
    logger.info(f"已填充 {len(equipment)} 条设备数据")


def _seed_production_lines(conn: sqlite3.Connection) -> None:
    """填入产线种子数据。"""
    lines = [
        ("LINE-001", "3号生产线", "壳体精加工", 280),
        ("LINE-002", "装配线B班", "液压油缸总成HC63-350", 420),
        ("LINE-003", "减速机总成装配线", "减速机总成", 14),
        ("LINE-004", "SMT产线3号", "电机控制器PCB(12层)", 200),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO production_lines (line_id, name, product, daily_capacity) "
        "VALUES (?, ?, ?, ?)",
        lines,
    )
    conn.commit()
    logger.info(f"已填充 {len(lines)} 条产线数据")


def _seed_materials(conn: sqlite3.Connection) -> None:
    """填入物料种子数据。"""
    materials = [
        ("MAT-001", "40Cr调质钢棒材", "Φ60×3000mm", "武汉钢铁集团", "¥12.50/kg"),
        ("MAT-002", "Y型密封圈(活塞)", "NBR丁腈橡胶", "广州密封件厂", "¥3.20/件"),
        ("MAT-003", "INA滚子轴承", "SL04-5008PP", "德国舍弗勒", "¥1,850/件"),
        ("MAT-004", "304冷轧不锈钢板", "2.0×1500×3000mm", "太钢不锈", "¥22,800/吨"),
        ("MAT-005", "45#调质钢棒材", "Φ80×3000mm", "鞍钢集团", "¥8.60/kg"),
        ("MAT-006", "二甲苯(溶剂)", "20L/桶 工业级", "中石化巴陵", "¥285/桶"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO materials (material_id, name, spec, supplier, unit_price) "
        "VALUES (?, ?, ?, ?, ?)",
        materials,
    )
    conn.commit()
    logger.info(f"已填充 {len(materials)} 条物料数据")


def _seed_quality_metrics(conn: sqlite3.Connection) -> None:
    """填入质量指标种子数据。"""
    metrics = [
        ("WO-20260501-005", 5.7, 0),
        ("WO-20260502-007", 3.0 / 420 * 100, 160),
        ("WO-20260504-015", 18.5, 45 * 13 / 60),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO quality_metrics (ticket_id, defect_rate, rework_hours) "
        "VALUES (?, ?, ?)",
        metrics,
    )
    conn.commit()
    logger.info(f"已填充 {len(metrics)} 条质量指标数据")


def _seed_db_schema_info(conn: sqlite3.Connection) -> None:
    """填入数据库 Schema 元数据（供 get_schema 工具使用）。"""
    from datetime import datetime as dt
    now = dt.now().strftime("%Y-%m-%d %H:%M:%S")
    schemas = [
        ("tickets", "id", "INTEGER", 0, 1, "主键自增ID"),
        ("tickets", "ticket_id", "TEXT", 0, 0, "工单唯一编号，格式 WO-YYYYMMDD-NNN"),
        ("tickets", "title", "TEXT", 0, 0, "工单标题"),
        ("tickets", "type", "TEXT", 0, 0, "工单类型：设备故障/质量异常/安全隐患/物料短缺/工艺问题/生产计划/环境监测"),
        ("tickets", "status", "TEXT", 0, 0, "工单状态：待处理/处理中/已解决/已关闭"),
        ("tickets", "priority", "TEXT", 0, 0, "优先级：紧急/高/中/低"),
        ("tickets", "assignee", "TEXT", 1, 0, "处理人姓名"),
        ("tickets", "created_at", "TEXT", 0, 0, "创建日期 YYYY-MM-DD"),
        ("tickets", "updated_at", "TEXT", 0, 0, "最后更新日期"),
        ("tickets", "description", "TEXT", 0, 0, "工单详细描述"),
        ("ticket_replies", "id", "INTEGER", 0, 1, "主键自增ID"),
        ("ticket_replies", "ticket_id", "TEXT", 0, 0, "关联工单编号"),
        ("ticket_replies", "content", "TEXT", 0, 0, "回复内容"),
        ("ticket_replies", "created_at", "TEXT", 0, 0, "回复时间"),
        ("conversations", "id", "INTEGER", 0, 1, "主键自增ID"),
        ("conversations", "title", "TEXT", 0, 0, "对话标题"),
        ("conversations", "created_at", "TEXT", 0, 0, "创建时间"),
        ("conversations", "updated_at", "TEXT", 0, 0, "最后更新时间"),
        ("conversations", "pinned", "INTEGER", 0, 0, "是否置顶 0/1"),
        ("conversation_messages", "id", "INTEGER", 0, 1, "主键自增ID"),
        ("conversation_messages", "conversation_id", "INTEGER", 0, 0, "关联对话ID"),
        ("conversation_messages", "role", "TEXT", 0, 0, "消息角色 user/assistant"),
        ("conversation_messages", "content", "TEXT", 0, 0, "消息内容"),
        ("conversation_messages", "steps", "TEXT", 1, 0, "推理步骤 JSON"),
        ("conversation_messages", "created_at", "TEXT", 0, 0, "消息时间"),
        # v5.0 移除死表: agent_actions, sql_templates, correction_rules
        # v3.3 领域表 FK 列
        ("tickets", "equipment_id", "TEXT", 1, 0, "关联设备ID FK → equipment"),
        ("tickets", "line_id", "TEXT", 1, 0, "关联产线ID FK → production_lines"),
        ("tickets", "material_id", "TEXT", 1, 0, "关联物料ID FK → materials"),
        # v3.3 领域表
        ("equipment", "equipment_id", "TEXT", 0, 1, "设备唯一编号"),
        ("equipment", "name", "TEXT", 0, 0, "设备名称"),
        ("equipment", "model", "TEXT", 1, 0, "设备型号"),
        ("equipment", "install_date", "TEXT", 1, 0, "安装日期"),
        ("equipment", "mtbf", "TEXT", 1, 0, "平均故障间隔"),
        ("equipment", "supplier", "TEXT", 1, 0, "供应商"),
        ("production_lines", "line_id", "TEXT", 0, 1, "产线唯一编号"),
        ("production_lines", "name", "TEXT", 0, 0, "产线名称"),
        ("production_lines", "product", "TEXT", 1, 0, "主要产品"),
        ("production_lines", "daily_capacity", "INTEGER", 1, 0, "日产能"),
        ("materials", "material_id", "TEXT", 0, 1, "物料唯一编号"),
        ("materials", "name", "TEXT", 0, 0, "物料名称"),
        ("materials", "spec", "TEXT", 1, 0, "规格"),
        ("materials", "supplier", "TEXT", 1, 0, "供应商"),
        ("materials", "unit_price", "TEXT", 1, 0, "单价"),
        ("quality_metrics", "metric_id", "INTEGER", 0, 1, "指标自增ID"),
        ("quality_metrics", "ticket_id", "TEXT", 0, 0, "关联工单编号 FK → tickets"),
        ("quality_metrics", "defect_rate", "REAL", 1, 0, "不良率 %"),
        ("quality_metrics", "rework_hours", "REAL", 1, 0, "返工工时"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO db_schema_info (table_name, column_name, data_type, is_nullable, is_primary_key, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        schemas,
    )
    conn.commit()
    logger.info(f"已填充 {len(schemas)} 条 Schema 元数据")


def query_tickets_db(
    ticket_type: str | None = None,
    status: str | None = None,
    date_range: str | None = None,
    priority: str | None = None,
) -> list[dict[str, Any]]:
    """按条件筛选工单列表。

    Args:
        priority: 优先级筛选，支持单值"紧急"或多值"紧急,高"（逗号分隔）。为None则不筛选。
    """
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
        if priority:
            priorities = [p.strip() for p in priority.split(",") if p.strip()]
            if len(priorities) == 1:
                query += " AND priority = ?"
                params.append(priorities[0])
            elif len(priorities) > 1:
                placeholders = ",".join("?" * len(priorities))
                query += f" AND priority IN ({placeholders})"
                params.extend(priorities)

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
