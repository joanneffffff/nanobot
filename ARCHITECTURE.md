# Agent Harness OS: 架构设计方案 (Syllabus Integrated)

## 1. 系统愿景
构建一个具备“深度思考、安全受控、自主进化”能力的 Agent 操作系统底座。

## 2. 核心架构层级

### A. 认知内核 (Cognitive Kernel) - 基于 Nanobot
* **Main Loop & Thinking Phase:** 严格区分 `Thinking`（分析规划）与 `Acting`（执行动作）阶段。在 ReAct 循环中强制引入隔离的思考环节，防止模型产生幻觉。
* **YOLO Philosophy:** 支持“全自动模式”，在受控沙盒内允许 Agent 连续执行多步操作，减少人类干预频率。
* **Parallel Execution:** 支持单轮对话中并行调用多个互不干扰的工具（如同时查询 3 个币种的价格）。

### B. 执行平面 (Execution Plane) - 双轨制任务引擎
* **标准轨 (Celery + API):** 处理确定性量化任务。
    * **Tool Registry:** 具备扩展性的工具注册中心。
    * **Webhook Callback:** 异步结果通过 Webhook 实时注入会话。
* **探索轨 (Subagent Sandbox):** 处理复杂投研与 Bug 修复。
    * **Subagent Spawner:** 动态派生具有独立上下文的子智能体。
    * **Self-Healing:** 具备错误感知与恢复提示词模板（Error Recovery Templates）。

### C. 记忆与上下文 (Context & Memory)
* **Tiered Compaction:** 采用阶梯式上下文压缩策略，根据 Token 消耗自动触发摘要总结。
* **Persistence:** 状态外部化，基于文件系统和向量库（Qdrant）的持久化记忆。
* **Session Management:** 物理层面的会话隔离，确保多用户/多策略并行不串扰。

### D. 稳定控制与安全 (Safety & Middleware)
* **System Reminders:** 定期注入系统提醒，防止 Agent 陷入“思考死循环”。
* **Middleware Proxy:** 对高危操作（交易、系统删除等）进行拦截，挂起任务并触发 IM 审批流。

## 3. 异步任务流转协议
所有执行单元完成后，需上报以下格式：
```json
{
  "task_id": "uuid",
  "source": "celery | subagent",
  "thinking": "执行过程中的关键反思点",
  "status": "success | error | timeout",
  "payload": { "data": "...", "files": ["url"] },
  "tracing": { "token_usage": 1200, "duration_ms": 5000 }
}
