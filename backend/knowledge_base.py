# -*- coding: utf-8 -*-
"""知识库 — 设备手册 + SOP 检查清单 + 巡检记录

为 Agent 提供开放环境下的结构化领域知识。数据均为内存存储。
"""

# ═══════════════════════════════════════════════════════════════
# 设备手册
# ═══════════════════════════════════════════════════════════════

EQUIPMENT_MANUALS = {
    "CNC-MC-003": {
        "equipment_id": "CNC-MC-003",
        "name": "CNC加工中心(3号线)",
        "model": "DMG MORI DMU 50",
        "install_date": "2019-03",
        "specs": {
            "主轴转速": "100-12000 rpm",
            "主轴功率": "35 kW",
            "主轴锥度": "HSK-A63",
            "冷却液容量": "400 L",
            "工作台尺寸": "800×500 mm",
            "定位精度": "±0.003 mm",
            "重复定位精度": "±0.002 mm",
        },
        "fault_codes": {
            "E01": {"name": "主轴过载", "cause": "切削力超出额定值或主轴轴承损伤", "action": "检查切削参数→检查主轴轴承→检查润滑系统"},
            "E02": {"name": "冷却液温度异常", "cause": "冷却液不足/冷却泵故障/散热器堵塞", "action": "检查液位→检查泵运转→清洗散热器"},
            "E03": {"name": "主轴振动超限", "cause": "轴承磨损/动平衡失效/刀具不平衡", "action": "检测振动频谱→检查轴承状态→动平衡校正"},
            "E04": {"name": "润滑压力低", "cause": "润滑油不足/滤芯堵塞/油泵故障", "action": "检查油位→更换滤芯→检查油泵"},
            "E05": {"name": "刀库换刀超时", "cause": "刀套定位偏差/气压不足/传感器故障", "action": "检查刀套位置→检查气压→检查传感器"},
        },
        "maintenance": {
            "主轴轴承": {"周期": "10000h 强制更换", "标准": "SKF 7014 ACD/P4A, 预紧力 34±2 Nm"},
            "冷却液": {"周期": "每 500h 更换", "标准": "ISO VG 32 主轴专用冷却液"},
            "润滑系统": {"周期": "每 500h 清洗滤芯+更换润滑油", "标准": "VG 68 导轨油, 滤芯精度 10μm"},
            "动平衡": {"周期": "每 2000h 或振动超 1.5mm/s 时", "标准": "G1 级, 残余不平衡量 <0.5 g·mm/kg"},
            "精度校准": {"周期": "每 4000h", "标准": "激光干涉仪校准, 定位精度 ±0.003mm"},
        },
        "common_issues": [
            {"symptom": "主轴异响", "causes": ["轴承磨损", "润滑不足", "刀具不平衡", "轴承安装预紧力不当"], "first_check": "检测振动频谱+检查润滑系统"},
            {"symptom": "加工精度超差", "causes": ["主轴轴承预紧力衰减", "导轨间隙增大", "热变形", "刀具磨损"], "first_check": "测量圆度+检查主轴温度+校准定位精度"},
            {"symptom": "表面振纹", "causes": ["砂轮/刀具动平衡失效", "主轴轴承损伤", "切削参数不当"], "first_check": "动平衡检测+振动频谱分析"},
        ],
    },
    "EQP-006": {
        "equipment_id": "EQP-006",
        "name": "液压机(HP-02)",
        "model": "315T四柱液压机",
        "install_date": "2017-06",
        "specs": {
            "公称压力": "3150 kN",
            "工作台尺寸": "1200×1000 mm",
            "滑块行程": "500 mm",
            "液压系统压力": "25 MPa",
            "闭合高度": "300-650 mm",
        },
        "fault_codes": {
            "H01": {"name": "液压系统压力低", "cause": "液压油不足/油泵磨损/溢流阀故障/管路泄漏", "action": "检查油位→检查管路→检查油泵→检查溢流阀"},
            "H02": {"name": "安全光幕触发", "cause": "光幕被遮挡/光幕光学窗口污染/接线松动/信号干扰", "action": "清洁光幕→检查接线→检查PLC信号→测试光幕灵敏度"},
            "H03": {"name": "滑块位置偏差", "cause": "位移传感器漂移/模具错位/液压缸内泄", "action": "校准位移传感器→检查模具位置→检查液压缸"},
            "H04": {"name": "油温过高", "cause": "冷却器效率下降/连续高速运行/液压油变质", "action": "检查冷却器→降低运行频率→检测油质"},
        },
        "maintenance": {
            "液压油": {"周期": "每 2000h 更换", "标准": "ISO VG 46 抗磨液压油, 清洁度 NAS 7 级"},
            "滤芯": {"周期": "每 500h 更换", "标准": "回油滤芯精度 10μm, 高压滤芯精度 5μm"},
            "密封件": {"周期": "每 8000h 更换", "标准": "全套液压缸密封+管路O型圈"},
            "安全光幕": {"周期": "每班次清洁+每月校准", "标准": "响应时间 <20ms, 最小检测物 30mm"},
        },
        "common_issues": [
            {"symptom": "安全光幕频繁误触发", "causes": ["光学窗口油雾污染", "接线端子氧化", "PLC输入滤波时间过短", "环境振动"], "first_check": "清洁光幕窗口→检查接线端子→检查PLC滤波参数"},
            {"symptom": "冲压件毛刺超标", "causes": ["模具间隙增大", "冲头磨损", "材料硬度变化", "模具错位"], "first_check": "测量模具间隙→检查冲头刃口→检查材料硬度"},
        ],
    },
    "IM-06": {
        "equipment_id": "IM-06",
        "name": "注塑机(6号)",
        "model": "海天 MA3200",
        "install_date": "2020-05",
        "specs": {
            "注射量": "1080 cm³",
            "锁模力": "3200 kN",
            "螺杆直径": "55 mm",
            "注射压力": "182 MPa",
            "温度控制": "4 区 PID 控制",
        },
        "fault_codes": {
            "P01": {"name": "温度控制异常", "cause": "热电偶故障/加热圈断路/继电器触点粘连/PID参数漂移", "action": "检查热电偶接线→检测加热圈电阻→检查继电器→重新自整定PID"},
            "P02": {"name": "注射压力不足", "cause": "喷嘴堵塞/螺杆磨损/液压系统压力低", "action": "清洗喷嘴→检查螺杆间隙→检查液压系统"},
            "P03": {"name": "锁模力不足", "cause": "液压缸内泄/模具平行度偏差/合模机构磨损", "action": "检查液压缸→检测模具平行度→检查合模机构"},
        },
        "maintenance": {
            "螺杆料筒": {"周期": "每 3000h 检查间隙", "标准": "螺杆与料筒间隙 <0.15mm"},
            "热电偶": {"周期": "每 2000h 更换", "标准": "K 型热电偶, 精度 ±1.5℃"},
            "液压油": {"周期": "每 2000h 更换", "标准": "ISO VG 46, 清洁度 NAS 8 级"},
        },
        "common_issues": [
            {"symptom": "制品黑点/脆化", "causes": ["材料过热分解", "温控失控", "螺杆转速过高", "料筒内有滞留物"], "first_check": "检测各区实际温度→检查温控器PID参数→检查螺杆转速→清洗料筒"},
        ],
    },
    "AGV-05": {
        "equipment_id": "AGV-05",
        "name": "AGV搬运车(5号)",
        "model": "海康威视 MR-Q3-300",
        "install_date": "2021-02",
        "specs": {
            "导航方式": "激光 SLAM + 惯性导航",
            "最大载荷": "300 kg",
            "定位精度": "±10 mm",
            "转弯半径": "1.0 m",
            "运行速度": "0.2-1.5 m/s",
        },
        "fault_codes": {},
        "maintenance": {
            "激光雷达": {"周期": "每月校准", "标准": "扫描频率 15Hz, 角度分辨率 0.1°"},
            "电池": {"周期": "每 500 循环检测", "标准": "磷酸铁锂 48V 60Ah, 容量 ≥80%"},
            "驱动轮": {"周期": "每 1000h 检查", "标准": "聚氨酯轮面磨损 <3mm"},
        },
        "common_issues": [
            {"symptom": "导航定位漂移", "causes": ["激光雷达视野遮挡", "地面反光标识磨损", "SLAM地图未更新", "环境光线剧烈变化"], "first_check": "检查激光雷达视野→检查地面标识→更新SLAM地图"},
            {"symptom": "碰撞障碍物", "causes": ["导航偏差累积", "障碍物检测传感器盲区", "路径规划未避让新障碍", "转弯通道过窄"], "first_check": "检查导航精度→检查传感器→检查路径规划→测量通道宽度"},
        ],
    },
    "AC-02": {
        "equipment_id": "AC-02",
        "name": "空压机(2号)",
        "model": "Atlas Copco GA90",
        "install_date": "2018-10",
        "specs": {
            "功率": "90 kW",
            "排气量": "16.5 m³/min",
            "工作压力": "6.0-7.5 bar",
            "冷却方式": "风冷",
            "变频器": "ABB ACS880 90kW",
        },
        "fault_codes": {
            "ERR-14": {"name": "电机过载", "cause": "机械卡滞/轴承损坏/变频器IGBT故障/电流传感器漂移", "action": "检查电机轴承→检查变频器输出电流→检查电流传感器→手盘转子确认无卡滞"},
            "ERR-22": {"name": "排气温度过高", "cause": "冷却器堵塞/环境温度过高/油路堵塞/温控阀故障", "action": "清洗冷却器→检查环境通风→检查油路→检查温控阀"},
            "ERR-31": {"name": "变频器故障", "cause": "IGBT模块过热/散热风扇故障/直流母线电压异常", "action": "检查散热风扇→检查IGBT温度→检查输入电压"},
        },
        "maintenance": {
            "空气滤芯": {"周期": "每 500h 更换", "标准": "过滤精度 1μm"},
            "油滤": {"周期": "每 2000h 更换", "标准": "螺杆专用油, 粘度 ISO VG 46"},
            "变频器": {"周期": "每 3000h 检查", "标准": "IGBT 模块温度 <85℃, 散热风扇正常"},
            "油气分离器": {"周期": "每 4000h 更换", "标准": "出口含油量 <3ppm"},
        },
        "common_issues": [
            {"symptom": "频繁跳闸", "causes": ["变频器IGBT过热", "电流传感器漂移", "电机轴承卡滞", "供电电压波动"], "first_check": "检查变频器散热风扇→检测实际运行电流→检查轴承→检测供电电压"},
            {"symptom": "全厂气压不足", "causes": ["空压机供气量下降", "管路泄漏", "用气量突然增大", "过滤器堵塞"], "first_check": "检测空压机排气量→检查管路压力→排查泄漏点→更换滤芯"},
        ],
    },
}

# ═══════════════════════════════════════════════════════════════
# SOP 检查清单
# ═══════════════════════════════════════════════════════════════

SOP_CHECKLISTS = {
    "安全光幕校验": {
        "code": "SOP-SAF-001",
        "周期": "每班次",
        "责任人": "操作工+当班线长",
        "步骤": [
            "1. 按下测试棒按钮，确认光幕触发急停",
            "2. 检查光幕发射端/接收端光学窗口是否清洁（目视无油雾/灰尘）",
            "3. 检查光幕安装支架是否紧固（用手轻推无晃动）",
            "4. 在 PLC 诊断页面确认光幕信号状态为 'OK'",
            "5. 填写《安全光幕点检表》并签字",
        ],
        "标准": "响应时间 <20ms, 最小检测物直径 30mm, 保护高度覆盖整个操作区",
        "异常处理": "光幕触发后需在 PLC 中确认原因再复位，不得直接屏蔽光幕运行",
    },
    "淬火工艺参数": {
        "code": "SOP-HT-002",
        "周期": "每批次首件确认 + 每 2h 巡检",
        "责任人": "热处理工艺员",
        "步骤": [
            "1. 确认感应器与工件同心度（偏差 <0.3mm）",
            "2. 确认淬火液温度在 25-35℃ 范围",
            "3. 确认加热功率和扫描速度与工艺卡一致",
            "4. 首件检测淬硬层深度和表面硬度（HRC 58-62）",
            "5. 每 2h 抽检 1 件做金相检验",
        ],
        "标准": "加热温度 820-860℃, 冷却速率 ≥80℃/s, 淬硬层深度 2.0-3.5mm, 表面硬度 HRC 58-62, 变形量 ≤0.35mm",
        "异常处理": "连续 3 件不合格立即停机调整，通知工艺主管。变形量 >0.5mm 的曲轴需校直后重新检测",
    },
    "动平衡校验": {
        "code": "SOP-BAL-003",
        "周期": "每班次点检 + 每 2000h 全面校验",
        "责任人": "设备维护工程师",
        "步骤": [
            "1. 使用便携式动平衡仪检测主轴/砂轮振动值",
            "2. 振动值 >1.5mm/s 执行现场动平衡校正",
            "3. 校正至 G1 级（残余不平衡量 <0.5 g·mm/kg）",
            "4. 记录振动值和校正量到设备履历表",
        ],
        "标准": "动平衡精度 G1 级, 残余不平衡量 <0.5 g·mm/kg, 振动速度 ≤1.5 mm/s RMS",
        "异常处理": "连续 2 次校正后仍超标的需拆下送专业动平衡机检测，可能为轴承损伤或转子变形",
    },
    "注塑温控系统校验": {
        "code": "SOP-IM-004",
        "周期": "每月自整定一次 + 每季度精度校验",
        "责任人": "设备维护工程师",
        "步骤": [
            "1. 使用标准温度计校准各温区热电偶（允差 ±1.5℃）",
            "2. 执行 PID 自整定程序",
            "3. 记录各温区设定值与实际值的最大偏差",
            "4. 检查加热圈电阻值（对比初始值，偏差 >10% 需更换）",
            "5. 检查固态继电器触点电阻（<0.1Ω）",
        ],
        "标准": "温度控制精度 ±0.5℃, 过冲量 <5℃, 升温速率 3-5℃/s",
        "异常处理": "PID 自整定 3 次仍超差的更换温控模块。热电偶反应迟钝的（响应时间 >3s）立即更换。",
    },
    "AGV 导航系统校验": {
        "code": "SOP-AGV-005",
        "周期": "每月 SLAM 地图更新 + 每季度导航精度测试",
        "责任人": "自动化工程师",
        "步骤": [
            "1. 检查仓库环境变化（新设备/货架/隔断），更新 SLAM 地图",
            "2. 检查地面反光标识完整性（破损面积 >30% 需更换）",
            "3. 在关键转弯点测试定位精度（偏差 <10mm）",
            "4. 测试障碍物检测传感器响应（检测距离 0.5-3m）",
            "5. 校验激光雷达扫描角度和分辨率",
        ],
        "标准": "定位精度 ±10mm, 转弯通道最小宽度 2.0m, 障碍物检测距离 0.5-3m, 安全减速距离 1.5m",
        "异常处理": "SLAM 地图更新后需空载跑 3 圈验证无碰撞风险。转弯通道宽度 <2.0m 的需设置禁停区和减速区。",
    },
    "空压机巡检": {
        "code": "SOP-AC-006",
        "周期": "每日巡检 + 每周全面检查",
        "责任人": "设备维护工程师",
        "步骤": [
            "1. 检查排气压力和温度（压力 6.0-7.5 bar, 排气温度 <95℃）",
            "2. 检查油气分离器压差（<0.8 bar）",
            "3. 检查变频器散热风扇运转和 IGBT 温度（<85℃）",
            "4. 检查管路系统气压（管网最低压力 ≥5.5 bar）",
            "5. 听运行异响、检查油位、记录运行小时数",
        ],
        "标准": "排气压力 6.0-7.5 bar, 管网压力 ≥5.5 bar, 排气温度 ≤95℃, IGBT 温度 ≤85℃, 含油量 ≤3ppm",
        "异常处理": "气压低于 5.5 bar 时先检查空压机和干燥机，再排查管路泄漏。变频器 IGBT 温度 >85℃ 需降低负载或停机检查散热系统。",
    },
}

# ═══════════════════════════════════════════════════════════════
# 巡检记录
# ═══════════════════════════════════════════════════════════════

INSPECTION_RECORDS = [
    # ── CNC-MC-003 最近 3 个月巡检 (每月 4 次) ──
    {"date": "2026-05-20", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "0.8 mm/s ✓", "冷却液温度": "37℃ ✓", "加工精度": "圆度 0.004mm ✓", "异响检查": "正常 ✓", "润滑压力": "正常 ✓"}},
    {"date": "2026-05-13", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "1.1 mm/s ⚠", "冷却液温度": "40℃ ⚠", "加工精度": "圆度 0.005mm ✓", "异响检查": "正常 ✓", "润滑压力": "正常 ✓"}},
    {"date": "2026-05-06", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "0.7 mm/s ✓", "冷却液温度": "36℃ ✓", "加工精度": "圆度 0.003mm ✓", "异响检查": "正常 ✓", "润滑压力": "正常 ✓"}},
    {"date": "2026-04-28", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "4.2 mm/s ✗", "冷却液温度": "42℃ ✗", "加工精度": "未检测", "异响检查": "尖锐异响 ✗", "润滑压力": "偏低 ✗"}},
    {"date": "2026-04-21", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "0.8 mm/s ✓", "冷却液温度": "35℃ ✓", "加工精度": "圆度 0.003mm ✓", "异响检查": "正常 ✓", "润滑压力": "正常 ✓"}},
    {"date": "2026-04-14", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "0.9 mm/s ✓", "冷却液温度": "36℃ ✓", "加工精度": "圆度 0.004mm ✓", "异响检查": "正常 ✓", "润滑压力": "正常 ✓"}},
    {"date": "2026-04-07", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "0.7 mm/s ✓", "冷却液温度": "35℃ ✓", "加工精度": "圆度 0.003mm ✓", "异响检查": "正常 ✓", "润滑压力": "正常 ✓"}},
    {"date": "2026-03-28", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "1.0 mm/s ✓", "冷却液温度": "37℃ ✓", "加工精度": "圆度 0.004mm ✓", "异响检查": "正常 ✓", "润滑压力": "正常 ✓"}},
    {"date": "2026-03-21", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "0.8 mm/s ✓", "冷却液温度": "35℃ ✓", "加工精度": "圆度 0.003mm ✓", "异响检查": "正常 ✓", "润滑压力": "正常 ✓"}},
    {"date": "2026-03-14", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "0.7 mm/s ✓", "冷却液温度": "36℃ ✓", "加工精度": "圆度 0.004mm ✓", "异响检查": "正常 ✓", "润滑压力": "正常 ✓"}},
    {"date": "2026-03-07", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "0.9 mm/s ✓", "冷却液温度": "35℃ ✓", "加工精度": "圆度 0.003mm ✓", "异响检查": "正常 ✓", "润滑压力": "正常 ✓"}},
    {"date": "2026-03-01", "equipment_id": "CNC-MC-003", "inspector": "张建国",
     "items": {"主轴振动": "0.8 mm/s ✓", "冷却液温度": "35℃ ✓", "加工精度": "圆度 0.003mm ✓", "异响检查": "正常 ✓", "润滑压力": "正常 ✓"}},

    # ── IM-06 注塑机 ──
    {"date": "2026-05-18", "equipment_id": "IM-06", "inspector": "李明辉",
     "items": {"温度控制": "±0.5℃ ✓", "注射压力": "182 MPa ✓", "制品外观": "正常 ✓", "螺杆转速": "120 rpm ✓"}},
    {"date": "2026-05-04", "equipment_id": "IM-06", "inspector": "李明辉",
     "items": {"温度控制": "±2.8℃ ⚠", "注射压力": "180 MPa ✓", "制品外观": "偶有黑点 ⚠", "螺杆转速": "120 rpm ✓"}},
    {"date": "2026-04-20", "equipment_id": "IM-06", "inspector": "李明辉",
     "items": {"温度控制": "±0.6℃ ✓", "注射压力": "181 MPa ✓", "制品外观": "正常 ✓", "螺杆转速": "120 rpm ✓"}},

    # ── EQP-006 冲压线 ──
    {"date": "2026-05-11", "equipment_id": "EQP-006", "inspector": "李明辉",
     "items": {"液压压力": "25 MPa ✓", "滑块位置": "±0.02mm ✓", "安全光幕": "正常 ✓", "冲压件毛刺": "0.04mm ✓"}},
    {"date": "2026-05-04", "equipment_id": "EQP-006", "inspector": "李明辉",
     "items": {"液压压力": "24 MPa ⚠", "滑块位置": "±0.05mm ⚠", "安全光幕": "间歇触发 ⚠", "冲压件毛刺": "0.06mm ⚠"}},
    {"date": "2026-04-27", "equipment_id": "EQP-006", "inspector": "李明辉",
     "items": {"液压压力": "25 MPa ✓", "滑块位置": "±0.02mm ✓", "安全光幕": "正常 ✓", "冲压件毛刺": "0.03mm ✓"}},

    # ── AC-02 空压机 ──
    {"date": "2026-05-17", "equipment_id": "AC-02", "inspector": "陈晓东",
     "items": {"排气压力": "6.2 bar ✓", "排气温度": "92℃ ⚠", "IGBT温度": "82℃ ⚠", "管网压力": "5.4 bar ⚠", "异响": "正常 ✓"}},
    {"date": "2026-05-10", "equipment_id": "AC-02", "inspector": "陈晓东",
     "items": {"排气压力": "6.5 bar ✓", "排气温度": "88℃ ✓", "IGBT温度": "78℃ ✓", "管网压力": "5.8 bar ✓", "异响": "正常 ✓"}},
    {"date": "2026-05-03", "equipment_id": "AC-02", "inspector": "陈晓东",
     "items": {"排气压力": "6.4 bar ✓", "排气温度": "90℃ ✓", "IGBT温度": "80℃ ✓", "管网压力": "5.7 bar ✓", "异响": "正常 ✓"}},
    {"date": "2026-04-26", "equipment_id": "AC-02", "inspector": "陈晓东",
     "items": {"排气压力": "6.3 bar ✓", "排气温度": "89℃ ✓", "IGBT温度": "79℃ ✓", "管网压力": "5.6 bar ✓", "异响": "正常 ✓"}},

    # ── AGV-05 ──
    {"date": "2026-05-19", "equipment_id": "AGV-05", "inspector": "李明辉",
     "items": {"定位精度": "±8mm ✓", "激光雷达": "正常 ✓", "电池容量": "85% ✓", "驱动轮磨损": "1.2mm ✓"}},
    {"date": "2026-05-12", "equipment_id": "AGV-05", "inspector": "李明辉",
     "items": {"定位精度": "±12mm ⚠", "激光雷达": "视野局部遮挡 ⚠", "电池容量": "82% ✓", "驱动轮磨损": "1.3mm ✓"}},
    {"date": "2026-04-19", "equipment_id": "AGV-05", "inspector": "李明辉",
     "items": {"定位精度": "±35mm ✗", "激光雷达": "视野遮挡 ✗", "电池容量": "78% ✓", "驱动轮磨损": "1.5mm ✓"}},
]

# ═══════════════════════════════════════════════════════════════
# 搜索函数
# ═══════════════════════════════════════════════════════════════


def search_equipment_manual(query: str) -> dict:
    """搜索设备手册：按设备编号/型号/故障码/关键词匹配。

    Returns:
        {"query": str, "results": [...], "count": int}
    """
    query_lower = query.lower().strip()
    results = []

    for eq_id, manual in EQUIPMENT_MANUALS.items():
        # 设备编号/型号直接匹配
        if eq_id.lower() in query_lower or manual["model"].lower() in query_lower or manual["name"] in query:
            results.append(_format_manual_entry(eq_id, manual, "direct"))
            continue

        # 故障码匹配
        for code, info in manual.get("fault_codes", {}).items():
            if code.lower() in query_lower or info["name"] in query:
                results.append(_format_fault_code(eq_id, manual, code, info))
                break

        # 常见问题关键词匹配
        for issue in manual.get("common_issues", []):
            if any(kw in query for kw in issue["symptom"].split("/")) or any(
                kw in query for kw in issue.get("causes", [])
            ):
                results.append(_format_common_issue(eq_id, manual, issue))
                break

        # 保养规程关键词匹配
        for maint_name, maint_info in manual.get("maintenance", {}).items():
            if maint_name in query:
                results.append(_format_maintenance(eq_id, manual, maint_name, maint_info))
                break

    if not results:
        # 全文关键词模糊搜索
        for eq_id, manual in EQUIPMENT_MANUALS.items():
            if _text_contains(manual, query):
                results.append(_format_manual_entry(eq_id, manual, "keyword"))
                if len(results) >= 3:
                    break

    # ── 搜索 SOP 检查清单 ──────────────────────────────────
    for sop_name, sop_info in SOP_CHECKLISTS.items():
        if _sop_matches(sop_name, sop_info, query):
            results.append(_format_sop_entry(sop_name, sop_info))
            if len(results) >= 5:
                break

    return {"query": query, "results": results, "count": len(results)}


def _sop_matches(name: str, info: dict, query: str) -> bool:
    """判断 SOP 是否与查询匹配。"""
    if name in query:
        return True
    if info.get("code", "").lower() in query.lower():
        return True
    for step in info.get("步骤", []):
        if any(kw in step for kw in query.split()):
            return True
    return False


def _format_sop_entry(name: str, info: dict) -> dict:
    return {
        "match_type": "sop",
        "sop_name": name,
        "code": info.get("code", ""),
        "周期": info.get("周期", ""),
        "责任人": info.get("责任人", ""),
        "步骤": info.get("步骤", []),
        "标准": info.get("标准", ""),
        "异常处理": info.get("异常处理", ""),
    }


def query_inspection_records(equipment_id: str, days: int = 30) -> dict:
    """查询设备最近 N 天巡检记录。

    Returns:
        {"equipment_id": str, "days": int, "records": [...], "count": int, "summary": str}
    """
    from datetime import datetime as dt, timedelta

    cutoff_date = (dt.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    records = [
        r for r in INSPECTION_RECORDS
        if r["equipment_id"] == equipment_id and r["date"] >= cutoff_date
    ]

    # 统计异常项
    abnormal_count = 0
    for r in records:
        for item, status in r["items"].items():
            if "✗" in status or "⚠" in status:
                abnormal_count += 1

    summary = (
        f"共 {len(records)} 条巡检记录, "
        f"{abnormal_count} 项异常/警告"
    )

    return {
        "equipment_id": equipment_id,
        "days": days,
        "records": records,
        "count": len(records),
        "summary": summary,
    }


def _format_manual_entry(eq_id: str, manual: dict, match_type: str) -> dict:
    return {
        "equipment_id": eq_id,
        "name": manual["name"],
        "model": manual["model"],
        "match_type": match_type,
        "specs": manual.get("specs", {}),
        "fault_codes": list(manual.get("fault_codes", {}).keys()),
        "maintenance": {k: v["周期"] for k, v in manual.get("maintenance", {}).items()},
        "common_issues": [i["symptom"] for i in manual.get("common_issues", [])],
    }


def _format_fault_code(eq_id: str, manual: dict, code: str, info: dict) -> dict:
    return {
        "equipment_id": eq_id,
        "name": manual["name"],
        "model": manual["model"],
        "match_type": "fault_code",
        "fault_code": code,
        "fault_name": info["name"],
        "cause": info["cause"],
        "action": info["action"],
    }


def _format_common_issue(eq_id: str, manual: dict, issue: dict) -> dict:
    return {
        "equipment_id": eq_id,
        "name": manual["name"],
        "model": manual["model"],
        "match_type": "common_issue",
        "symptom": issue["symptom"],
        "causes": issue["causes"],
        "first_check": issue["first_check"],
    }


def _format_maintenance(eq_id: str, manual: dict, name: str, info: dict) -> dict:
    return {
        "equipment_id": eq_id,
        "name": manual["name"],
        "model": manual["model"],
        "match_type": "maintenance",
        "item": name,
        "周期": info["周期"],
        "标准": info["标准"],
    }


def _text_contains(manual: dict, query: str) -> bool:
    """检查手册中是否包含查询关键词（模糊匹配）。"""
    import json
    text = json.dumps(manual, ensure_ascii=False).lower()
    for word in query.lower().split():
        if word in text:
            return True
    return False
