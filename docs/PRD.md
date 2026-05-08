# PRD: MCP智能工单Agent系统

## 项目定位

基于MCP协议的标准化Agent系统，演示AI Agent如何通过标准协议调用企业内部业务工具，完成智能工单查询与分析。该项目直接对标企业AI Agent开发岗位。

## 核心用户故事

1. 作为用户，通过自然语言向Agent提问（如“查询最近一周的退款工单”）。
2. Agent能自主理解意图，选择并调用合适的MCP工具。
3. 可完整看到Agent的推理过程（Thought-Action-Observation）。

## MVP功能

### F1：MCP工具服务层

- 实现两个工具：query_tickets（工单查询）、analyze_tickets（工单分析）。
- 工具使用模拟的企业工单数据。
- 工具服务遵循MCP协议基本规范。

### F2：Agent智能调度层

- 使用LangChain Agent完成意图识别与工具调度。
- Agent根据自然语言输入自主决定调用哪个工具，支持多轮对话。

### F3：ReAct推理可视化

- 在前端展示Thought（思考）、Action（动作）、Observation（观察）步骤。

### F4：前端聊天界面

- 使用Streamlit构建。
- 主区域展示对话历史。
- 侧边栏展示推理步骤和工具调用详情。

## 验收标准

- 输入“最近一周有哪些退款工单？”，Agent调用query_tickets并返回结果。
- 输入“帮我分析一下这个月工单的趋势”，Agent调用analyze_tickets并给出统计结论。
- 输入“你好”，Agent不调用任何工具，直接回复问候语。
