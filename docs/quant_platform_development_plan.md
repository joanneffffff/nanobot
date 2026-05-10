# 量化平台二次开发计划

> 分阶段渐进式开发，每阶段验证达标后再进入下一阶段

---

## 一、开发原则

### 1.1 核心原则

1. **渐进式开发** - 每个阶段独立可验证，不依赖后续阶段
2. **向后兼容** - 新功能不影响已有功能，可随时回滚
3. **测试先行** - 每阶段完成前必须通过全量测试
4. **Git Tag 里程碑** - 每阶段完成后打 Tag，作为回滚点

### 1.2 阶段验收流程

```
阶段开发完成
    ↓
运行全量测试 (pytest tests/ -v)
    ↓
手动回归测试（验证前面所有阶段）
    ↓
创建 Git Tag (git tag stageN-xxx)
    ↓
更新文档，记录已完成功能
    ↓
评审确认后进入下一阶段
```

### 1.3 回滚策略

如果某阶段开发影响前面功能：

```bash
# 回滚到上一个稳定 Tag
git checkout stageN-xxx

# 或重置当前分支
git reset --hard stageN-xxx
```

---

## 二、Stage 0: 环境准备与基线验证

**目标**: 确保 nanobot 原生功能正常运行
**周期**: 1-2 天
**依赖**: 无

### 2.1 任务清单

| 任务 | 预估时间 | 说明 |
|------|----------|------|
| 0.1 安装 nanobot 依赖 | 0.5h | `pip install -e ".[dev]"` |
| 0.2 配置 LLM Provider | 0.5h | 配置 OpenAI/Anthropic API Key |
| 0.3 启动 gateway | 0.5h | `nanobot gateway` |
| 0.4 测试 OpenAI 兼容 API | 1h | curl 测试 /v1/chat/completions |
| 0.5 测试 WebUI | 1h | 浏览器访问，验证对话功能 |
| 0.6 测试工具调用 | 2h | 让 Agent 调用 filesystem/shell 工具 |
| 0.7 创建基线测试脚本 | 1h | 记录所有测试用例，供后续回归 |

### 2.2 验收标准

| 测试项 | 验证方法 | 预期结果 |
|--------|----------|----------|
| Gateway 启动 | `curl localhost:8765/health` | `{"status": "ok"}` |
| API 对话 | POST /v1/chat/completions | 返回正常响应 |
| 工具调用 | 让 Agent 读文件 | 成功读取并返回内容 |
| WebUI 访问 | 浏览器打开 | 页面正常显示，可对话 |

### 2.3 基线测试脚本

```bash
#!/bin/bash
# tests/baseline/stage0_baseline.sh

echo "=== Stage 0 Baseline Tests ==="

# 1. Health check
echo "1. Health check..."
curl -s http://localhost:8765/health | jq .

# 2. Chat completion
echo "2. Chat completion..."
curl -s -X POST http://localhost:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}' | jq .

# 3. Tool call (filesystem)
echo "3. Tool call test..."
curl -s -X POST http://localhost:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Read the file /etc/hostname"}]}' | jq .

echo "=== Stage 0 Baseline Tests Complete ==="
```

### 2.4 完成标志

```bash
# 创建 Git Tag
git tag -a stage0-baseline -m "Stage 0: 基线验证完成"

# 验证
git tag -l "stage*"
```

---

## 三、Stage 1: 量化 API 对接

**目标**: nanobot 能调用 quant_system 的 API
**周期**: 3-5 天
**依赖**: Stage 0 完成
**回滚点**: `stage0-baseline`

### 3.1 任务清单

| 任务 | 预估时间 | 说明 |
|------|----------|------|
| 1.1 设计量化工具接口 | 2h | 定义 get_price, run_backtest 等工具签名 |
| 1.2 实现 get_price 工具 | 2h | 调用 quant_system /api/data/price |
| 1.3 实现 get_kline 工具 | 2h | 调用 quant_system /api/data/kline |
| 1.4 实现 run_backtest 工具 | 4h | 调用 quant_system /backtest/run-async |
| 1.5 实现 get_position 工具 | 2h | 调用 quant_system /api/trading/position |
| 1.6 实现 execute_trade 工具 (Mock) | 2h | 先 Mock，不真实执行 |
| 1.7 注册工具到 Tool Registry | 2h | 修改 nanobot 配置 |
| 1.8 编写单元测试 | 4h | 测试每个工具 |
| 1.9 回归测试 | 2h | 验证 Stage 0 功能不受影响 |

### 3.2 技术方案

**文件**: `nanobot/agent/tools/quant_tools.py` (新建)

```python
"""量化平台工具集"""
import httpx
from nanobot.agent.tools import tool

QUANT_API_URL = "http://localhost:8001"

@tool
async def get_price(symbol: str) -> dict:
    """获取股票实时价格

    Args:
        symbol: 股票代码，如 sh.600519

    Returns:
        包含价格信息的字典
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{QUANT_API_URL}/api/data/price",
            params={"symbol": symbol}
        )
        return response.json()

@tool
async def get_kline(symbol: str, period: str = "1d", limit: int = 100) -> dict:
    """获取股票K线数据

    Args:
        symbol: 股票代码
        period: 周期 (1d/1w/1m)
        limit: 返回条数

    Returns:
        K线数据列表
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{QUANT_API_URL}/api/data/kline",
            params={"symbol": symbol, "period": period, "limit": limit}
        )
        return response.json()

@tool
async def run_backtest(strategy: dict, symbols: list, start_date: str, end_date: str) -> dict:
    """运行回测任务

    Args:
        strategy: 策略配置
        symbols: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        任务信息，包含 task_id
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{QUANT_API_URL}/backtest/run-async",
            json={
                "strategy": strategy,
                "symbols": symbols,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        return response.json()

@tool
async def execute_trade(symbol: str, action: str, quantity: int) -> dict:
    """执行交易（当前为 Mock）

    Args:
        symbol: 股票代码
        action: 买入/卖出
        quantity: 数量

    Returns:
        模拟执行结果
    """
    # Stage 1 先 Mock，Stage 3 再实现真实审批流程
    return {
        "status": "mock",
        "message": "交易请求已记录（Mock模式）",
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
    }
```

### 3.3 工具注册

**文件**: `nanobot/config/tools.py` (修改)

```python
# 添加量化工具到工具列表
QUANT_TOOLS = [
    "nanobot.agent.tools.quant_tools.get_price",
    "nanobot.agent.tools.quant_tools.get_kline",
    "nanobot.agent.tools.quant_tools.run_backtest",
    "nanobot.agent.tools.quant_tools.execute_trade",
]
```

### 3.4 验收标准

| 测试项 | 验证方法 | 预期结果 |
|--------|----------|----------|
| get_price | 问 Agent "茅台现在多少钱" | 返回价格信息 |
| get_kline | 问 Agent "茅台最近K线" | 返回K线数据 |
| run_backtest | 让 Agent 运行简单回测 | 返回 task_id |
| 原有工具 | 让 Agent 读文件 | 仍然正常工作 |

### 3.5 回归测试脚本

```bash
#!/bin/bash
# tests/baseline/stage1_regression.sh

echo "=== Stage 1 Regression Tests ==="

# 运行 Stage 0 基线测试
./tests/baseline/stage0_baseline.sh

# Stage 1 新增测试
echo "4. Quant API - get_price..."
curl -s -X POST http://localhost:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "查询茅台 sh.600519 的价格"}]}' | jq .

echo "5. Quant API - get_kline..."
curl -s -X POST http://localhost:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "获取茅台最近10天的日K线"}]}' | jq .

echo "=== Stage 1 Regression Tests Complete ==="
```

### 3.6 完成标志

```bash
# 运行测试
pytest tests/test_quant_tools.py -v

# 回归测试
./tests/baseline/stage1_regression.sh

# 创建 Git Tag
git tag -a stage1-quant-api -m "Stage 1: 量化API对接完成"
```

---

## 四、Stage 2: Thinking 阶段剥离

**目标**: 交易决策前有独立思考，高风险操作需确认
**周期**: 3-5 天
**依赖**: Stage 1 完成
**回滚点**: `stage1-quant-api`

### 4.1 任务清单

| 任务 | 预估时间 | 说明 |
|------|----------|------|
| 2.1 设计 Thought 数据结构 | 1h | 定义思考结果的结构 |
| 2.2 实现 ThinkingEngine | 4h | 独立思考引擎，不调用工具 |
| 2.3 设计思考 Prompt 模板 | 2h | 量化场景专用模板 |
| 2.4 实现审批判断逻辑 | 2h | 根据工具类型判断是否需要审批 |
| 2.5 修改 AgentLoop | 4h | 在 act 前插入 think 阶段 |
| 2.6 实现审批等待机制 | 4h | 异步等待用户确认 |
| 2.7 编写单元测试 | 4h | 测试思考阶段和审批流程 |
| 2.8 回归测试 | 2h | 验证 Stage 0-1 功能不受影响 |

### 4.2 技术方案

**文件**: `nanobot/agent/thinking.py` (新建)

```python
"""独立思考阶段实现"""
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class ActionType(Enum):
    READ = "read"        # 只读操作
    ANALYSIS = "analysis"  # 分析操作
    TRADE = "trade"      # 交易操作

@dataclass
class Thought:
    """思考结果"""
    analysis: str                    # 分析内容
    proposed_actions: list[dict]     # 拟执行动作
    risk_assessment: str             # 风险评估
    confidence: float                # 置信度 0-1
    requires_approval: bool          # 是否需要人工确认
    approval_reason: Optional[str]   # 需要确认的原因

class ThinkingEngine:
    """独立思考引擎"""

    # 需要审批的操作
    APPROVAL_REQUIRED = {"execute_trade", "cancel_order"}

    async def think(self, context: dict, user_input: str) -> Thought:
        """执行独立思考（不调用任何工具）"""

        # 构建思考 Prompt
        prompt = self._build_think_prompt(context, user_input)

        # 调用 LLM（不传递工具定义）
        response = await self.provider.generate(
            prompt=prompt,
            tools=None,  # 关键：不传递工具
            system_prompt=self._get_thinking_system_prompt(),
        )

        # 解析思考结果
        thought = self._parse_thought(response.content)

        # 判断是否需要审批
        thought.requires_approval = self._check_approval_required(thought)

        return thought

    def _check_approval_required(self, thought: Thought) -> bool:
        """检查是否需要人工确认"""
        for action in thought.proposed_actions:
            if action.get("tool") in self.APPROVAL_REQUIRED:
                return True
        # 低置信度也需要确认
        if thought.confidence < 0.7:
            return True
        return False

    def _get_thinking_system_prompt(self) -> str:
        return """
你是量化交易分析师。现在进入独立思考阶段。

你的任务：
1. 分析用户需求和市场情况
2. 设计可能的策略或操作方案
3. 评估每个方案的风险和收益
4. 给出建议和置信度

重要：
- 本阶段只能思考，不能执行任何操作
- 对于交易类操作，必须给出详细风险评估
- 涉及实盘交易，必须等待人工确认

输出格式：
## 市场分析
[分析内容]

## 策略建议
[建议内容]

## 风险评估
[风险评估]

## 拟执行操作
- [ ] 操作1: ...
- [ ] 操作2: ...

## 置信度
X/10
"""
```

### 4.3 AgentLoop 改造

**文件**: `nanobot/agent/loop.py` (修改)

```python
class AgentLoop:
    """Agent 主循环 - 增加 Thinking 阶段"""

    def __init__(self, ...):
        self.thinking_engine = ThinkingEngine(provider)

    async def run(self, user_input: str, session_key: str) -> AsyncIterator[LoopEvent]:
        # Phase 1: Observe
        context = await self.observe(user_input, session_key)
        yield LoopEvent(phase="observe", data=context)

        # Phase 2: Think (新增)
        thought = await self.thinking_engine.think(context, user_input)
        yield LoopEvent(phase="think", data=thought)

        # 检查是否需要审批
        if thought.requires_approval:
            yield LoopEvent(phase="awaiting_approval", data={
                "thought": thought,
                "message": "此操作需要人工确认"
            })
            approval = await self.wait_for_approval(session_key)
            if not approval.approved:
                yield LoopEvent(phase="cancelled", data={"reason": approval.reason})
                return

        # Phase 3: Act
        async for result in self.act(thought.proposed_actions, context):
            yield LoopEvent(phase="act", data=result)

        # Phase 4: Reflect
        reflection = await self.reflect(thought, context)
        yield LoopEvent(phase="reflect", data=reflection)
```

### 4.4 验收标准

| 测试项 | 验证方法 | 预期结果 |
|--------|----------|----------|
| 查询操作 | 问 Agent "茅台价格" | 直接返回，无需确认 |
| 分析操作 | 让 Agent 运行回测 | 先输出分析，再执行 |
| 交易操作 | 让 Agent 买入股票 | 弹出确认框 |
| 确认后执行 | 点击确认 | 正确执行 |
| 取消后中止 | 点击取消 | 正确中止 |
| 原有功能 | 测试 Stage 0-1 功能 | 不受影响 |

### 4.5 完成标志

```bash
# 运行测试
pytest tests/test_thinking.py -v

# 回归测试
./tests/baseline/stage2_regression.sh

# 创建 Git Tag
git tag -a stage2-thinking-phase -m "Stage 2: Thinking阶段剥离完成"
```

---

## 五、Stage 3: 安全中间件

**目标**: 权限控制、限流、审计日志
**周期**: 3-5 天
**依赖**: Stage 2 完成
**回滚点**: `stage2-thinking-phase`

### 5.1 任务清单

| 任务 | 预估时间 | 说明 |
|------|----------|------|
| 3.1 设计 Middleware 接口 | 1h | 抽象中间件基类 |
| 3.2 实现 PermissionMiddleware | 3h | 权限校验 |
| 3.3 实现 RateLimitMiddleware | 3h | 限流控制 |
| 3.4 实现 AuditMiddleware | 3h | 审计日志 |
| 3.5 实现 MiddlewareChain | 2h | 中间件链 |
| 3.6 集成到 ToolRegistry | 2h | 工具执行前经过中间件 |
| 3.7 创建数据库表 | 1h | audit_logs 表 |
| 3.8 编写单元测试 | 4h | 测试各中间件 |
| 3.9 回归测试 | 2h | 验证 Stage 0-2 功能 |

### 5.2 技术方案

**文件**: `nanobot/middleware/__init__.py` (新建)

```python
"""安全中间件"""
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

@dataclass
class InterceptResult:
    """拦截结果"""
    blocked: bool
    reason: Optional[str] = None
    requires_approval: bool = False

class Middleware(ABC):
    """中间件基类"""

    @abstractmethod
    async def intercept(self, tool_name: str, params: dict, context: dict) -> Optional[InterceptResult]:
        """拦截检查，返回 None 表示放行"""
        pass

class MiddlewareChain:
    """中间件链"""

    def __init__(self):
        self.middlewares: list[Middleware] = []

    def add(self, middleware: Middleware):
        self.middlewares.append(middleware)
        return self

    async def process(self, tool_name: str, params: dict, context: dict) -> Optional[InterceptResult]:
        for middleware in self.middlewares:
            result = await middleware.intercept(tool_name, params, context)
            if result is not None:
                return result
        return None
```

**文件**: `nanobot/middleware/permission.py`

```python
class PermissionMiddleware(Middleware):
    """权限校验中间件"""

    TOOL_LEVELS = {
        "get_price": "read",
        "get_kline": "read",
        "run_backtest": "analysis",
        "execute_trade": "trade",
    }

    USER_LEVELS = {
        "guest": "read",
        "user": "analysis",
        "vip": "trade",
        "admin": "admin",
    }

    LEVEL_HIERARCHY = ["read", "analysis", "trade", "admin"]

    async def intercept(self, tool_name: str, params: dict, context: dict) -> Optional[InterceptResult]:
        user_role = context.get("user_role", "guest")
        tool_level = self.TOOL_LEVELS.get(tool_name, "admin")
        user_level = self.USER_LEVELS.get(user_role, "guest")

        if self.LEVEL_HIERARCHY.index(user_level) < self.LEVEL_HIERARCHY.index(tool_level):
            return InterceptResult(
                blocked=True,
                reason=f"权限不足：需要 {tool_level} 级别，当前 {user_level}"
            )
        return None
```

### 5.3 验收标准

| 测试项 | 验证方法 | 预期结果 |
|--------|----------|----------|
| 权限不足 | guest 用户调用 execute_trade | 被拦截，返回权限错误 |
| 权限足够 | vip 用户调用 execute_trade | 通过权限检查 |
| 限流生效 | 短时间大量请求 | 超过阈值被拦截 |
| 审计日志 | 执行任意操作 | 日志记录到数据库 |
| 原有功能 | 测试 Stage 0-2 功能 | 不受影响 |

### 5.4 完成标志

```bash
# 运行测试
pytest tests/test_middleware.py -v

# 回归测试
./tests/baseline/stage3_regression.sh

# 创建 Git Tag
git tag -a stage3-security-middleware -m "Stage 3: 安全中间件完成"
```

---

## 六、Stage 4: 异步任务桥接

**目标**: Celery 长任务通过 Webhook 回调
**周期**: 3-5 天
**依赖**: Stage 3 完成
**回滚点**: `stage3-security-middleware`

### 6.1 任务清单

| 任务 | 预估时间 | 说明 |
|------|----------|------|
| 4.1 实现 CeleryBridge | 4h | 任务提交和状态跟踪 |
| 4.2 实现 Webhook 接收端点 | 2h | /ai/webhook/task_complete |
| 4.3 实现会话恢复机制 | 4h | 结果注入到正确会话 |
| 4.4 修改 run_backtest 工具 | 2h | 使用 CeleryBridge |
| 4.5 前端进度显示 | 4h | 显示任务状态 |
| 4.6 编写单元测试 | 4h | 测试异步流程 |
| 4.7 回归测试 | 2h | 验证 Stage 0-3 功能 |

### 6.2 技术方案

**文件**: `nanobot/agent/tools/celery_bridge.py` (新建)

```python
"""Celery 任务桥接"""
import asyncio
import httpx
from typing import Optional

class CeleryBridge:
    """Celery 任务桥接器"""

    def __init__(self, quant_api_url: str, webhook_base_url: str):
        self.quant_api_url = quant_api_url
        self.webhook_base_url = webhook_base_url
        self.pending_tasks: dict[str, asyncio.Event] = {}
        self.task_results: dict[str, dict] = {}

    async def submit_task(
        self,
        task_name: str,
        params: dict,
        session_key: str,
    ) -> dict:
        """提交任务"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.quant_api_url}/api/tasks/submit",
                json={
                    "task_name": task_name,
                    "params": params,
                    "webhook_url": f"{self.webhook_base_url}/ai/webhook/task_complete",
                    "session_key": session_key,
                }
            )

        task_id = response.json()["task_id"]

        # 创建等待事件
        event = asyncio.Event()
        self.pending_tasks[task_id] = event

        return {"task_id": task_id, "status": "pending"}

    async def wait_for_result(self, task_id: str, timeout: float = 300.0) -> Optional[dict]:
        """等待任务结果"""
        if task_id not in self.pending_tasks:
            return None

        event = self.pending_tasks[task_id]
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self.task_results.get(task_id)
        except asyncio.TimeoutError:
            return {"status": "timeout"}
        finally:
            del self.pending_tasks[task_id]

    async def handle_webhook(self, task_id: str, result: dict):
        """处理 Webhook 回调"""
        if task_id in self.pending_tasks:
            self.task_results[task_id] = result
            self.pending_tasks[task_id].set()
```

### 6.3 验收标准

| 测试项 | 验证方法 | 预期结果 |
|--------|----------|----------|
| 任务提交 | 运行回测 | 返回 task_id，状态 pending |
| Webhook 接收 | 模拟 Celery 回调 | 结果正确接收 |
| 结果注入 | 检查会话 | 结果出现在正确会话 |
| 前端进度 | 观察前端 | 显示任务执行中 → 完成 |
| 原有功能 | 测试 Stage 0-3 功能 | 不受影响 |

### 6.4 完成标志

```bash
# 运行测试
pytest tests/test_celery_bridge.py -v

# 回归测试
./tests/baseline/stage4_regression.sh

# 创建 Git Tag
git tag -a stage4-async-bridge -m "Stage 4: 异步任务桥接完成"
```

---

## 七、Stage 5: IM 控制（飞书）

**目标**: 通过 IM 触发 Agent 操作
**周期**: 3-5 天
**依赖**: Stage 4 完成
**回滚点**: `stage4-async-bridge`

### 7.1 任务清单

| 任务 | 预估时间 | 说明 |
|------|----------|------|
| 5.1 飞书机器人配置 | 2h | 创建应用，获取凭证 |
| 5.2 实现飞书消息接收 | 4h | Webhook 接收飞书事件 |
| 5.3 实现消息路由 | 2h | 飞书消息 → nanobot 会话 |
| 5.4 实现审批推送 | 4h | 高风险操作推送到飞书 |
| 5.5 实现审批回调 | 4h | 飞书审批后恢复执行 |
| 5.6 编写单元测试 | 4h | 测试飞书集成 |
| 5.7 回归测试 | 2h | 验证 Stage 0-4 功能 |

### 7.2 验收标准

| 测试项 | 验证方法 | 预期结果 |
|--------|----------|----------|
| 消息接收 | 飞书发消息 | Agent 正确响应 |
| 审批推送 | 触发交易操作 | 推送到飞书 |
| 审批确认 | 飞书点击确认 | 正确执行 |
| 审批拒绝 | 飞书点击拒绝 | 正确中止 |
| 原有功能 | 测试 Stage 0-4 功能 | 不受影响 |

### 7.3 完成标志

```bash
# 运行测试
pytest tests/test_feishu.py -v

# 回归测试
./tests/baseline/stage5_regression.sh

# 创建 Git Tag
git tag -a stage5-im-integration -m "Stage 5: IM控制完成"
```

---

## 八、Stage 6: 进化记忆与优化

**目标**: 策略经验沉淀，性能优化
**周期**: 3-5 天
**依赖**: Stage 5 完成
**回滚点**: `stage5-im-integration`

### 8.1 任务清单

| 任务 | 预估时间 | 说明 |
|------|----------|------|
| 6.1 实现 ContextCompaction | 4h | 上下文压缩 |
| 6.2 实现策略记忆保存 | 4h | 每次策略总结存库 |
| 6.3 实现记忆注入 | 3h | 新对话加载历史经验 |
| 6.4 实现 Subagent 委派 | 4h | 复杂任务隔离执行 |
| 6.5 性能优化 | 4h | 缓存、并发优化 |
| 6.6 编写单元测试 | 4h | 测试记忆和优化 |
| 6.7 全量回归测试 | 4h | 验证所有阶段功能 |

### 8.2 验收标准

| 测试项 | 验证方法 | 预期结果 |
|--------|----------|----------|
| 上下文压缩 | 模拟长对话 | Token 减少 |
| 策略记忆 | 完成策略对话 | 数据库有记录 |
| 记忆注入 | 新对话 | 参考历史经验 |
| Subagent | 委派复杂任务 | 隔离执行成功 |
| 全量回归 | 所有阶段测试 | 全部通过 |

### 8.3 完成标志

```bash
# 运行全量测试
pytest tests/ -v

# 全量回归测试
./tests/baseline/stage6_full_regression.sh

# 创建 Git Tag
git tag -a stage6-memory-optimization -m "Stage 6: 进化记忆与优化完成"

# 最终发布 Tag
git tag -a v1.0.0 -m "量化平台 AI Agent 二次开发完成"
```

---

## 九、测试矩阵

### 9.1 阶段测试对照表

| 测试项 | Stage 0 | Stage 1 | Stage 2 | Stage 3 | Stage 4 | Stage 5 | Stage 6 |
|--------|---------|---------|---------|---------|---------|---------|---------|
| Gateway 启动 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| API 对话 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 原生工具 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 量化工具 | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Thinking 阶段 | - | - | ✅ | ✅ | ✅ | ✅ | ✅ |
| 审批流程 | - | - | ✅ | ✅ | ✅ | ✅ | ✅ |
| 权限控制 | - | - | - | ✅ | ✅ | ✅ | ✅ |
| 限流 | - | - | - | ✅ | ✅ | ✅ | ✅ |
| 审计日志 | - | - | - | ✅ | ✅ | ✅ | ✅ |
| 异步任务 | - | - | - | - | ✅ | ✅ | ✅ |
| 飞书集成 | - | - | - | - | - | ✅ | ✅ |
| 记忆系统 | - | - | - | - | - | - | ✅ |

### 9.2 回归测试脚本模板

```bash
#!/bin/bash
# tests/baseline/stageN_regression.sh

set -e

echo "=== Stage N Regression Tests ==="

# 运行上一阶段的回归测试
if [ -f "tests/baseline/stage$((N-1))_regression.sh" ]; then
    ./tests/baseline/stage$((N-1))_regression.sh
fi

# Stage N 新增测试
echo "Stage N specific tests..."

# 测试 1
# 测试 2
# ...

echo "=== Stage N Regression Tests Complete ==="
```

---

## 十、交付清单

### 10.1 代码交付

| 文件 | Stage | 说明 |
|------|-------|------|
| `nanobot/agent/tools/quant_tools.py` | 1 | 量化工具集 |
| `nanobot/agent/thinking.py` | 2 | Thinking 引擎 |
| `nanobot/middleware/__init__.py` | 3 | Middleware 框架 |
| `nanobot/middleware/permission.py` | 3 | 权限中间件 |
| `nanobot/middleware/rate_limit.py` | 3 | 限流中间件 |
| `nanobot/middleware/audit.py` | 3 | 审计中间件 |
| `nanobot/agent/tools/celery_bridge.py` | 4 | Celery 桥接 |
| `nanobot/channels/feishu.py` | 5 | 飞书集成 |
| `nanobot/session/compaction.py` | 6 | 上下文压缩 |
| `nanobot/memory/evolutionary.py` | 6 | 进化记忆 |

### 10.2 测试交付

| 测试类型 | 覆盖率要求 |
|----------|------------|
| 单元测试 | > 80% |
| 集成测试 | 关键路径 100% |
| 回归测试 | 所有阶段功能 |

### 10.3 文档交付

- [ ] API 文档
- [ ] 架构设计文档
- [ ] 部署指南
- [ ] 测试报告

---

**文档版本**: v3.0
**创建日期**: 2026-05-10
**更新说明**: 采用分阶段渐进式开发，每阶段独立可验证
