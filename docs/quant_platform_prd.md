# 量化平台二次开发 PRD

> 基于《从 0 开始构建 Agent Harness》课程理念，将 nanobot 改造为量化场景专用的 AI Agent 脚手架

---

## 一、项目背景与目标

### 1.1 现有系统

| 系统 | 技术栈 | 端口 | 定位 |
|------|--------|------|------|
| nanobot | Python + React/TS | 8765 | 通用 AI Agent 框架 |
| quant_system | Python + FastAPI | 8001 | 量化交易后端引擎 |
| quant_frontend_naive | Vue 3 + Naive UI | 5173 | 量化交易前端界面 |

### 1.2 核心目标

将 nanobot 从「通用 Framework」改造为「量化专用 Harness」，实现：
1. **Thinking 阶段剥离** - 交易决策前的独立思考与人工确认
2. **异步任务桥接** - Celery 长任务的回调唤醒机制
3. **安全防御纵深** - Middleware 拦截高危操作
4. **进化记忆系统** - 策略经验的沉淀与复用

---

## 二、架构设计：从 Framework 到 Harness

### 2.1 课程核心理念

> "框架正在坍塌：像写操作系统一样，实现底层 Harness"

传统 Framework 是「调用我」，Harness 是「我调用你」。量化场景需要：
- **可控的执行平面** - 不是被动响应，而是主动编排
- **透明的决策过程** - 每一步思考都可追溯、可干预
- **渐进的能力扩展** - 工具、技能、记忆都是可插拔模块

### 2.2 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Harness 控制层                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Main Loop (课程 02)                               │   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │   │
│  │  │ Observe  │ → │  Think   │ → │   Act    │ → │ Reflect  │        │   │
│  │  │ (感知)   │   │ (思考)   │   │ (执行)   │   │ (反思)   │        │   │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────┼───────────────────────────────────┐   │
│  │                         Middleware 层 (课程 16)                      │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │   │
│  │  │ 权限校验   │  │ 审批拦截   │  │ 限流控制   │  │ 审计日志   │    │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Tool Registry  │     │  Context Layer  │     │  Memory System  │
│   (课程 05-08)  │     │   (课程 10-14)  │     │     (课程 13)   │
│                 │     │                 │     │                 │
│  - get_price    │     │  - Session 隔离 │     │  - 策略记忆     │
│  - run_backtest │     │  - Compaction   │     │  - 经验沉淀     │
│  - execute_trade│     │  - Error Recover│     │  - 待办管理     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
          │                         │
          └─────────────────────────┘
                      │
          ┌───────────▼───────────┐
          │   Execution Plane     │
          │   (课程 09, 17)       │
          │                       │
          │  - Celery Bridge      │
          │  - Subagent 委派      │
          │  - 飞书集成           │
          └───────────────────────┘
```

---

## 三、核心模块设计

### 3.1 核心引擎改造 (课程 02-04)

#### 3.1.1 Main Loop 重写

**课程要点**：手写 Agent 的 Main Loop，不依赖任何框架的抽象。

**量化场景改造**：

```python
# nanobot/agent/loop.py 改造
from enum import Enum
from typing import AsyncIterator
import asyncio

class LoopPhase(Enum):
    OBSERVE = "observe"      # 感知：接收用户输入、市场数据
    THINK = "think"          # 思考：独立 Thinking 阶段
    ACT = "act"              # 执行：调用工具
    REFLECT = "reflect"      # 反思：总结、沉淀记忆

class AgentLoop:
    """量化 Agent 主循环 - Harness 核心"""

    async def run(self, user_input: str, session_key: str) -> AsyncIterator[LoopEvent]:
        """主循环入口 - 生成器模式，支持流式输出"""

        # Phase 1: Observe - 感知阶段
        context = await self.observe(user_input, session_key)
        yield LoopEvent(phase=LoopPhase.OBSERVE, data={"context": context})

        # Phase 2: Think - 独立思考阶段（课程 03）
        thought = await self.think(context)
        yield LoopEvent(phase=LoopPhase.THINK, data={"thought": thought})

        # 检查是否需要人工确认
        if self._requires_human_approval(thought):
            yield LoopEvent(
                phase=LoopPhase.THINK,
                data={"status": "awaiting_approval", "thought": thought}
            )
            approval = await self.wait_for_approval(session_key)
            if not approval.approved:
                yield LoopEvent(phase=LoopPhase.REFLECT, data={"cancelled": True})
                return

        # Phase 3: Act - 执行阶段（支持并发，课程 08）
        async for action_result in self.act(thought, context):
            yield LoopEvent(phase=LoopPhase.ACT, data=action_result)

        # Phase 4: Reflect - 反思阶段（课程 13 记忆沉淀）
        reflection = await self.reflect(thought, context)
        await self.persist_memory(reflection, session_key)
        yield LoopEvent(phase=LoopPhase.REFLECT, data={"reflection": reflection})

    async def observe(self, user_input: str, session_key: str) -> dict:
        """感知阶段：收集上下文"""
        return {
            "user_input": user_input,
            "session_history": await self.load_session_history(session_key),
            "market_context": await self.fetch_market_context(),  # 量化特有
            "user_preferences": await self.load_user_preferences(session_key),
        }

    async def think(self, context: dict) -> Thought:
        """独立思考阶段 - 课程 03 核心改造"""
        # 构建思考 Prompt
        think_prompt = self.build_think_prompt(context)

        # 调用 LLM 进行思考（不执行任何工具）
        response = await self.provider.generate(
            prompt=think_prompt,
            tools=None,  # 思考阶段不调用工具
            system_prompt=self.get_think_system_prompt(),
        )

        return Thought(
            analysis=response.content,
            proposed_actions=self.parse_proposed_actions(response.content),
            risk_assessment=self.extract_risk_assessment(response.content),
            confidence=self.extract_confidence(response.content),
        )

    async def act(self, thought: Thought, context: dict) -> AsyncIterator[ActionResult]:
        """执行阶段 - 支持并发工具调用（课程 08）"""

        # 识别可并行的工具调用
        parallel_groups = self.identify_parallel_groups(thought.proposed_actions)

        for group in parallel_groups:
            if len(group) == 1:
                # 单个工具，直接执行
                result = await self.execute_tool(group[0])
                yield result
            else:
                # 多个独立工具，并发执行
                results = await asyncio.gather(*[
                    self.execute_tool(action) for action in group
                ])
                for result in results:
                    yield result

    async def reflect(self, thought: Thought, context: dict) -> Reflection:
        """反思阶段 - 策略经验沉淀"""
        return Reflection(
            what_worked=self.analyze_successes(thought),
            what_failed=self.analyze_failures(thought),
            lessons_learned=self.extract_lessons(thought),
            strategy_summary=self.summarize_strategy(thought),
        )
```

#### 3.1.2 Thinking 阶段剥离 (课程 03)

**课程要点**：在 ReAct 循环中剥离独立的 Thinking 阶段，实现"慢思考与自省"。

**量化场景改造**：

```python
# nanobot/agent/thinking.py 新增
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class ThoughtType(Enum):
    ANALYSIS = "analysis"           # 市场分析
    STRATEGY_DESIGN = "strategy"    # 策略设计
    RISK_ASSESSMENT = "risk"        # 风险评估
    TRADE_DECISION = "trade"        # 交易决策

@dataclass
class Thought:
    """独立思考结果"""
    type: ThoughtType
    analysis: str                    # 分析内容
    proposed_actions: list[dict]     # 拟执行动作
    risk_assessment: dict            # 风险评估
    confidence: float                # 置信度 0-1
    requires_approval: bool          # 是否需要人工确认
    approval_reason: Optional[str]   # 需要确认的原因

class ThinkingEngine:
    """独立思考引擎"""

    # 需要人工确认的操作类型
    APPROVAL_REQUIRED = {
        "execute_trade",
        "cancel_order",
        "modify_strategy",
        "system_config",
    }

    async def think(self, context: dict, user_input: str) -> Thought:
        """执行独立思考"""

        # 1. 分析用户意图
        intent = await self.analyze_intent(user_input)

        # 2. 构建思考 Prompt
        prompt = self.build_think_prompt(intent, context)

        # 3. 调用 LLM（不执行工具）
        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=self.get_thinking_system_prompt(),
        )

        # 4. 解析思考结果
        thought = self.parse_thought(response.content)

        # 5. 判断是否需要人工确认
        thought.requires_approval = self._check_approval_required(thought)
        if thought.requires_approval:
            thought.approval_reason = self._generate_approval_reason(thought)

        return thought

    def _check_approval_required(self, thought: Thought) -> bool:
        """检查是否需要人工确认"""
        for action in thought.proposed_actions:
            if action.get("tool") in self.APPROVAL_REQUIRED:
                return True
        # 高风险操作：置信度低于阈值
        if thought.confidence < 0.7 and thought.type == ThoughtType.TRADE_DECISION:
            return True
        return False

    def get_thinking_system_prompt(self) -> str:
        """思考阶段的系统提示"""
        return """
你是一个量化交易分析师。现在进入独立思考阶段。

你的任务是：
1. 分析用户的需求和市场情况
2. 设计可能的策略或操作方案
3. 评估每个方案的风险和收益
4. 给出你的建议和置信度

重要：
- 在这个阶段，你只能思考和输出分析，不能执行任何操作
- 对于交易类操作，必须给出详细的风险评估
- 如果涉及实盘交易，必须等待人工确认

输出格式：
## 市场分析
...

## 策略建议
...

## 风险评估
...

## 拟执行操作
- [ ] 操作1: ...
- [ ] 操作2: ...

## 置信度
X/10

## 是否需要人工确认
是/否，原因：...
"""
```

---

### 3.2 工具系统改造 (课程 05-08)

#### 3.2.1 Tool Registry 重构 (课程 05)

**课程要点**：构建高扩展性的 Tool Registry 与分发机制。

```python
# nanobot/agent/tools/registry.py 改造
from typing import Callable, Any
from dataclasses import dataclass
from enum import IntEnum
import inspect

class ToolLevel(IntEnum):
    """工具安全等级"""
    READ = 1        # 只读：查询价格、持仓
    ANALYSIS = 2    # 分析：回测、策略分析
    TRADE = 3       # 交易：下单、撤单
    ADMIN = 4       # 管理：系统配置

@dataclass
class ToolMeta:
    """工具元信息"""
    name: str
    description: str
    level: ToolLevel
    parameters_schema: dict
    handler: Callable
    timeout: float = 30.0
    retry_count: int = 0
    requires_confirmation: bool = False

class ToolRegistry:
    """工具注册中心"""

    def __init__(self):
        self._tools: dict[str, ToolMeta] = {}
        self._middlewares: list[Callable] = []

    def register(
        self,
        name: str,
        level: ToolLevel = ToolLevel.READ,
        requires_confirmation: bool = False,
    ):
        """工具注册装饰器"""
        def decorator(func: Callable):
            # 提取参数 schema
            sig = inspect.signature(func)
            params_schema = self._extract_params_schema(sig)

            # 判断是否需要确认
            needs_confirm = requires_confirmation or level >= ToolLevel.TRADE

            self._tools[name] = ToolMeta(
                name=name,
                description=func.__doc__ or "",
                level=level,
                parameters_schema=params_schema,
                handler=func,
                requires_confirmation=needs_confirm,
            )
            return func
        return decorator

    async def execute(
        self,
        name: str,
        params: dict,
        context: dict,
    ) -> Any:
        """执行工具 - 经过中间件链"""
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool '{name}' not found")

        tool = self._tools[name]

        # 执行中间件链
        for middleware in self._middlewares:
            result = await middleware(tool, params, context)
            if result is not None:  # 中间件拦截
                return result

        # 执行工具
        return await tool.handler(**params)

    def add_middleware(self, middleware: Callable):
        """添加中间件"""
        self._middlewares.append(middleware)


# 量化工具注册
registry = ToolRegistry()

@registry.register("get_price", level=ToolLevel.READ)
async def get_price(symbol: str) -> dict:
    """获取股票实时价格"""
    # 实现省略
    pass

@registry.register("run_backtest", level=ToolLevel.ANALYSIS)
async def run_backtest(strategy: dict, symbols: list, start_date: str, end_date: str) -> dict:
    """运行回测"""
    # 实现省略
    pass

@registry.register("execute_trade", level=ToolLevel.TRADE)
async def execute_trade(symbol: str, action: str, quantity: int) -> dict:
    """执行交易 - 需要 Level 3 权限"""
    # 实现省略
    pass
```

#### 3.2.2 并发工具调用 (课程 08)

**课程要点**：让 Agent 在单轮中并行调用多个互相独立的工具。

```python
# nanobot/agent/tools/parallel.py 新增
import asyncio
from typing import list
from dataclasses import dataclass

@dataclass
class ToolCall:
    name: str
    params: dict
    dependencies: list[str] = None  # 依赖的其他工具调用

class ParallelExecutor:
    """并发工具执行器"""

    async def execute_parallel(self, calls: list[ToolCall]) -> list[dict]:
        """并发执行多个工具调用"""

        # 1. 构建依赖图
        graph = self._build_dependency_graph(calls)

        # 2. 拓扑排序，识别可并行的组
        groups = self._topological_sort(graph)

        # 3. 按组执行
        results = {}
        for group in groups:
            # 同一组内的调用可以并发执行
            group_results = await asyncio.gather(*[
                self._execute_single(call, results)
                for call in group
            ])
            for call, result in zip(group, group_results):
                results[call.name] = result

        return [results[call.name] for call in calls]

    def _build_dependency_graph(self, calls: list[ToolCall]) -> dict:
        """构建依赖图"""
        graph = {call.name: set() for call in calls}
        for call in calls:
            if call.dependencies:
                for dep in call.dependencies:
                    if dep in graph:
                        graph[call.name].add(dep)
        return graph

    def _topological_sort(self, graph: dict) -> list[list[str]]:
        """拓扑排序，返回可并行的组"""
        groups = []
        remaining = set(graph.keys())

        while remaining:
            # 找出没有依赖的节点
            no_deps = {
                node for node in remaining
                if not graph[node] & remaining
            }
            if not no_deps:
                raise CircularDependencyError("Circular dependency detected")

            groups.append(list(no_deps))
            remaining -= no_deps

        return groups


# 使用示例
async def example_parallel_execution():
    executor = ParallelExecutor()

    # 用户问："分析茅台和五粮液的走势，并对比"
    calls = [
        ToolCall(name="get_price", params={"symbol": "sh.600519"}),
        ToolCall(name="get_price", params={"symbol": "sz.000858"}),
        ToolCall(name="get_kline", params={"symbol": "sh.600519", "period": "1d"}),
        ToolCall(name="get_kline", params={"symbol": "sz.000858", "period": "1d"}),
        # compare 依赖前四个调用
        ToolCall(
            name="compare_stocks",
            params={},
            dependencies=["get_price_0", "get_price_1", "get_kline_0", "get_kline_1"]
        ),
    ]

    results = await executor.execute_parallel(calls)
```

---

### 3.3 上下文工程 (课程 10-14)

#### 3.3.1 Context Compaction (课程 12)

**课程要点**：基于阶梯降级的 Context Compaction 策略，突破内存限制。

```python
# nanobot/session/compaction.py 新增
from enum import Enum
from typing import list
from dataclasses import dataclass

class CompactionStage(Enum):
    """压缩阶段"""
    FULL = "full"              # 完整保留
    SUMMARY = "summary"        # 摘要保留
    KEY_POINTS = "key_points"  # 关键点
    META_ONLY = "meta_only"    # 仅元信息

@dataclass
class CompactionRule:
    """压缩规则"""
    max_age_turns: int         # 超过多少轮后压缩
    target_stage: CompactionStage

class ContextCompactor:
    """上下文压缩器 - 课程 12 核心实现"""

    DEFAULT_RULES = [
        CompactionRule(max_age_turns=5, target_stage=CompactionStage.SUMMARY),
        CompactionRule(max_age_turns=10, target_stage=CompactionStage.KEY_POINTS),
        CompactionRule(max_age_turns=20, target_stage=CompactionStage.META_ONLY),
    ]

    def __init__(self, max_tokens: int = 4000, rules: list[CompactionRule] = None):
        self.max_tokens = max_tokens
        self.rules = rules or self.DEFAULT_RULES

    async def compact(self, messages: list[dict], current_tokens: int) -> list[dict]:
        """执行压缩"""
        if current_tokens <= self.max_tokens:
            return messages

        total_turns = len(messages)
        compacted = []

        for i, msg in enumerate(messages):
            age = total_turns - i - 1  # 消息年龄（轮数）
            stage = self._determine_stage(age)

            compacted_msg = await self._compact_message(msg, stage)
            compacted.append(compacted_msg)

        return compacted

    def _determine_stage(self, age: int) -> CompactionStage:
        """根据消息年龄确定压缩阶段"""
        for rule in self.rules:
            if age >= rule.max_age_turns:
                return rule.target_stage
        return CompactionStage.FULL

    async def _compact_message(self, msg: dict, stage: CompactionStage) -> dict:
        """压缩单条消息"""
        if stage == CompactionStage.FULL:
            return msg

        content = msg.get("content", "")

        if stage == CompactionStage.SUMMARY:
            # 使用 LLM 生成摘要
            summary = await self._generate_summary(content)
            return {**msg, "content": f"[摘要] {summary}"}

        elif stage == CompactionStage.KEY_POINTS:
            # 提取关键点
            key_points = await self._extract_key_points(content)
            return {**msg, "content": f"[关键点] {key_points}"}

        else:  # META_ONLY
            # 仅保留元信息
            return {
                **msg,
                "content": f"[历史消息: {len(content)}字符, {msg.get('role', 'unknown')}]"
            }

    async def _generate_summary(self, content: str) -> str:
        """使用 LLM 生成摘要"""
        # 调用 LLM 生成摘要
        prompt = f"请用一句话总结以下内容的核心要点：\n\n{content[:2000]}"
        # ... LLM 调用
        pass

    async def _extract_key_points(self, content: str) -> str:
        """提取关键决策点"""
        # 提取交易决策、策略变更等关键信息
        pass
```

#### 3.3.2 错误自愈 (课程 14)

**课程要点**：上下文感知的 Error Recovery 提示模板注入机制。

```python
# nanobot/agent/error_recovery.py 新增
from typing import Optional
from dataclasses import dataclass

@dataclass
class ErrorContext:
    """错误上下文"""
    error_type: str
    error_message: str
    tool_name: Optional[str]
    params: Optional[dict]
    attempt_count: int
    previous_attempts: list[dict]

class ErrorRecovery:
    """错误自愈机制 - 课程 14"""

    RECOVERY_PROMPTS = {
        "tool_not_found": """
工具 '{tool_name}' 不存在。
可用工具列表：{available_tools}
请检查工具名称是否正确，或使用其他工具实现类似功能。
""",
        "permission_denied": """
权限不足：{error_message}
当前用户角色：{user_role}
所需权限等级：{required_level}
请联系管理员提升权限，或使用其他方式完成任务。
""",
        "timeout": """
操作超时：{tool_name}
参数：{params}
可能原因：
1. 数据量过大
2. 网络延迟
3. 服务繁忙

建议：
1. 缩小查询范围
2. 增加超时时间
3. 稍后重试
""",
        "rate_limit": """
请求频率超限：{error_message}
当前限制：{limit} 次/分钟
请等待 {retry_after} 秒后重试。
""",
        "validation_error": """
参数验证失败：{error_message}
工具：{tool_name}
参数：{params}
期望格式：{expected_schema}

请修正参数后重试。
""",
    }

    async def recover(
        self,
        error: Exception,
        context: dict,
        attempt_count: int,
    ) -> Optional[str]:
        """尝试错误恢复"""

        error_context = self._build_error_context(error, context, attempt_count)

        # 1. 检查是否超过最大重试次数
        if attempt_count >= 3:
            return self._generate_final_failure_prompt(error_context)

        # 2. 获取恢复提示
        recovery_prompt = self._get_recovery_prompt(error_context)

        # 3. 注入上下文感知的建议
        recovery_prompt = self._inject_context_suggestions(recovery_prompt, context)

        return recovery_prompt

    def _get_recovery_prompt(self, error_context: ErrorContext) -> str:
        """获取恢复提示模板"""
        template = self.RECOVERY_PROMPTS.get(
            error_context.error_type,
            "发生错误：{error_message}\n请分析错误原因并尝试其他方法。"
        )
        return template.format(
            tool_name=error_context.tool_name,
            error_message=error_context.error_message,
            params=error_context.params,
            attempt_count=error_context.attempt_count,
        )

    def _inject_context_suggestions(self, prompt: str, context: dict) -> str:
        """注入上下文感知的建议"""
        suggestions = []

        # 基于历史尝试给出建议
        if context.get("previous_attempts"):
            tried_tools = [a.get("tool") for a in context["previous_attempts"]]
            suggestions.append(f"已尝试的工具：{', '.join(tried_tools)}")

        # 基于用户意图给出建议
        if context.get("user_intent"):
            suggestions.append(f"用户意图：{context['user_intent']}")

        if suggestions:
            prompt += "\n\n上下文建议：\n" + "\n".join(f"- {s}" for s in suggestions)

        return prompt
```

---

### 3.4 安全与中间件 (课程 15-16)

#### 3.4.1 Middleware 拦截机制 (课程 16)

**课程要点**：利用 Middleware 实现高危命令拦截与飞书人工审批。

```python
# nanobot/middleware/security.py 新增
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any
from dataclasses import dataclass
import asyncio
import hmac
import hashlib
import time

@dataclass
class InterceptResult:
    """拦截结果"""
    blocked: bool
    reason: Optional[str] = None
    requires_approval: bool = False
    approval_request_id: Optional[str] = None

class Middleware(ABC):
    """中间件基类"""

    @abstractmethod
    async def intercept(
        self,
        tool: ToolMeta,
        params: dict,
        context: dict
    ) -> Optional[InterceptResult]:
        """拦截检查，返回 None 表示放行"""
        pass

class PermissionMiddleware(Middleware):
    """权限校验中间件"""

    USER_LEVELS = {
        "guest": ToolLevel.READ,
        "user": ToolLevel.ANALYSIS,
        "vip": ToolLevel.TRADE,
        "admin": ToolLevel.ADMIN,
    }

    async def intercept(
        self,
        tool: ToolMeta,
        params: dict,
        context: dict
    ) -> Optional[InterceptResult]:
        user_role = context.get("user_role", "guest")
        user_level = self.USER_LEVELS.get(user_role, ToolLevel.READ)

        if user_level < tool.level:
            return InterceptResult(
                blocked=True,
                reason=f"权限不足：需要 {tool.level.name} 级别，当前 {user_level.name}"
            )
        return None

class RateLimitMiddleware(Middleware):
    """限流中间件"""

    def __init__(self, redis_client, limits: dict[str, int]):
        self.redis = redis_client
        self.limits = limits  # {"get_price": 100, "run_backtest": 10}

    async def intercept(
        self,
        tool: ToolMeta,
        params: dict,
        context: dict
    ) -> Optional[InterceptResult]:
        user_id = context.get("user_id")
        limit = self.limits.get(tool.name, 60)

        key = f"rate_limit:{user_id}:{tool.name}"
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, 60)  # 1分钟窗口

        if current > limit:
            return InterceptResult(
                blocked=True,
                reason=f"请求频率超限：{tool.name} 限制 {limit} 次/分钟"
            )
        return None

class HumanApprovalMiddleware(Middleware):
    """人工审批中间件 - 课程 16 核心"""

    def __init__(self, secret_key: str, timeout: float = 300.0):
        self.secret_key = secret_key
        self.timeout = timeout
        self.pending_requests: dict[str, asyncio.Event] = {}
        self.request_data: dict[str, dict] = {}

    async def intercept(
        self,
        tool: ToolMeta,
        params: dict,
        context: dict
    ) -> Optional[InterceptResult]:
        # 检查是否需要审批
        if not tool.requires_confirmation:
            return None

        # 创建审批请求
        request_id = self._generate_request_id(tool, params, context)
        self.request_data[request_id] = {
            "tool": tool.name,
            "params": params,
            "context": context,
            "created_at": time.time(),
        }

        # 创建等待事件
        event = asyncio.Event()
        self.pending_requests[request_id] = event

        # 返回需要审批
        return InterceptResult(
            blocked=False,
            requires_approval=True,
            approval_request_id=request_id,
        )

    async def wait_for_approval(self, request_id: str) -> bool:
        """等待审批结果"""
        if request_id not in self.pending_requests:
            return False

        event = self.pending_requests[request_id]
        try:
            await asyncio.wait_for(event.wait(), timeout=self.timeout)
            return self.request_data[request_id].get("approved", False)
        except asyncio.TimeoutError:
            return False
        finally:
            del self.pending_requests[request_id]
            del self.request_data[request_id]

    async def approve(self, request_id: str, user_id: str) -> bool:
        """审批通过"""
        if request_id not in self.pending_requests:
            return False

        self.request_data[request_id]["approved"] = True
        self.request_data[request_id]["approved_by"] = user_id
        self.request_data[request_id]["signature"] = self._sign(request_id, user_id)

        self.pending_requests[request_id].set()
        return True

    async def reject(self, request_id: str, user_id: str, reason: str) -> bool:
        """审批拒绝"""
        if request_id not in self.pending_requests:
            return False

        self.request_data[request_id]["approved"] = False
        self.request_data[request_id]["rejected_by"] = user_id
        self.request_data[request_id]["reject_reason"] = reason

        self.pending_requests[request_id].set()
        return True

    def _sign(self, request_id: str, user_id: str) -> str:
        """生成 HMAC 签名"""
        data = f"{request_id}:{user_id}:{time.time()}"
        return hmac.new(
            self.secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

    def _generate_request_id(self, tool: ToolMeta, params: dict, context: dict) -> str:
        """生成请求 ID"""
        import uuid
        return str(uuid.uuid4())


# 中间件链组装
class MiddlewareChain:
    """中间件链"""

    def __init__(self):
        self.middlewares: list[Middleware] = []

    def add(self, middleware: Middleware):
        self.middlewares.append(middleware)
        return self

    async def process(
        self,
        tool: ToolMeta,
        params: dict,
        context: dict
    ) -> Optional[InterceptResult]:
        """执行中间件链"""
        for middleware in self.middlewares:
            result = await middleware.intercept(tool, params, context)
            if result is not None:
                return result
        return None


# 使用示例
middleware_chain = MiddlewareChain()
middleware_chain.add(PermissionMiddleware())
middleware_chain.add(RateLimitMiddleware(redis_client, {
    "get_price": 100,
    "run_backtest": 10,
    "execute_trade": 5,
}))
middleware_chain.add(HumanApprovalMiddleware(secret_key="your-secret-key"))

# 注册到 ToolRegistry
registry.add_middleware(middleware_chain.process)
```

#### 3.4.2 飞书审批集成 (课程 09, 16)

```python
# nanobot/channels/feishu_approval.py 新增
import httpx
from dataclasses import dataclass

@dataclass
class FeishuApprovalConfig:
    app_id: str
    app_secret: str
    approval_code: str  # 审批流程代码

class FeishuApprovalChannel:
    """飞书审批通道 - 课程 09 + 16"""

    def __init__(self, config: FeishuApprovalConfig):
        self.config = config
        self.access_token = None

    async def send_approval_request(
        self,
        request_id: str,
        tool: str,
        params: dict,
        context: dict,
        thought: str,
    ) -> str:
        """发送审批请求到飞书"""

        # 获取 access_token
        if not self.access_token:
            await self._refresh_token()

        # 构建审批内容
        content = self._build_approval_content(tool, params, thought)

        # 调用飞书审批 API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/approval/v4/instances",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "approval_code": self.config.approval_code,
                    "form": content,
                    "open_id": context.get("feishu_open_id"),
                }
            )

        return response.json()["data"]["instance_code"]

    def _build_approval_content(self, tool: str, params: dict, thought: str) -> dict:
        """构建审批表单内容"""
        return {
            "form_fields": [
                {"name": "操作类型", "value": tool},
                {"name": "操作参数", "value": str(params)},
                {"name": "AI 分析", "value": thought},
                {"name": "风险等级", "value": self._assess_risk(tool)},
            ]
        }

    async def handle_approval_callback(self, instance_code: str, approved: bool):
        """处理飞书审批回调"""
        # 根据 instance_code 找到对应的 request_id
        # 调用 HumanApprovalMiddleware.approve 或 reject
        pass
```

---

### 3.5 Subagent 委派 (课程 17)

**课程要点**：引入 Subagent 来隔离复杂探索任务的上下文瓶颈。

```python
# nanobot/agent/subagent.py 新增
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum
import asyncio

class SubagentType(Enum):
    RESEARCH = "research"      # 投研分析
    BACKTEST = "backtest"      # 回测执行
    MONITOR = "monitor"        # 监控任务
    REPORT = "report"          # 报告生成

@dataclass
class SubagentTask:
    """子代理任务"""
    type: SubagentType
    description: str
    context: dict
    timeout: float = 300.0
    max_turns: int = 10

@dataclass
class SubagentResult:
    """子代理结果"""
    success: bool
    output: Any
    summary: str  # 给主 Agent 的摘要
    tokens_used: int

class SubagentManager:
    """子代理管理器 - 课程 17"""

    def __init__(self, main_loop: AgentLoop):
        self.main_loop = main_loop
        self.active_subagents: dict[str, asyncio.Task] = {}

    async def delegate(self, task: SubagentTask) -> SubagentResult:
        """委派任务给子代理"""

        # 1. 创建隔离的上下文
        isolated_context = self._create_isolated_context(task)

        # 2. 创建子代理
        subagent = self._create_subagent(task.type, isolated_context)

        # 3. 执行任务
        try:
            result = await asyncio.wait_for(
                subagent.run(task.description),
                timeout=task.timeout
            )

            # 4. 生成摘要
            summary = await self._generate_summary(result)

            return SubagentResult(
                success=True,
                output=result,
                summary=summary,
                tokens_used=subagent.tokens_used,
            )

        except asyncio.TimeoutError:
            return SubagentResult(
                success=False,
                output=None,
                summary=f"子代理任务超时：{task.description}",
                tokens_used=0,
            )

    def _create_isolated_context(self, task: SubagentTask) -> dict:
        """创建隔离上下文 - 只传递必要信息"""
        return {
            "task_type": task.type.value,
            "task_description": task.description,
            "user_preferences": task.context.get("user_preferences"),
            "market_context": task.context.get("market_context"),
            # 不传递完整的会话历史，避免上下文污染
        }

    def _create_subagent(self, type: SubagentType, context: dict) -> AgentLoop:
        """创建子代理实例"""
        # 根据类型配置不同的工具集和提示词
        configs = {
            SubagentType.RESEARCH: {
                "tools": ["get_price", "get_kline", "get_financial", "search_news"],
                "system_prompt": "你是投研分析专家...",
            },
            SubagentType.BACKTEST: {
                "tools": ["run_backtest", "get_backtest_result", "analyze_strategy"],
                "system_prompt": "你是回测分析专家...",
            },
            SubagentType.MONITOR: {
                "tools": ["get_realtime", "check_signals", "send_alert"],
                "system_prompt": "你是监控专家...",
            },
            SubagentType.REPORT: {
                "tools": ["generate_report", "export_data"],
                "system_prompt": "你是报告生成专家...",
            },
        }

        config = configs.get(type, {})
        return AgentLoop(
            provider=self.main_loop.provider,
            tools=config.get("tools", []),
            system_prompt=config.get("system_prompt", ""),
            context=context,
        )

    async def _generate_summary(self, result: Any) -> str:
        """生成给主 Agent 的摘要"""
        # 使用 LLM 压缩结果
        pass


# 主 Agent 使用示例
class MainAgentLoop(AgentLoop):
    """主 Agent 循环 - 支持子代理委派"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subagent_manager = SubagentManager(self)

    async def act(self, thought: Thought, context: dict) -> AsyncIterator[ActionResult]:
        """执行阶段 - 支持子代理委派"""

        for action in thought.proposed_actions:
            # 检查是否需要委派
            if self._should_delegate(action):
                # 委派给子代理
                task = SubagentTask(
                    type=self._get_subagent_type(action),
                    description=action.get("description", ""),
                    context=context,
                )
                result = await self.subagent_manager.delegate(task)

                yield ActionResult(
                    tool="subagent",
                    result=result.output,
                    summary=result.summary,
                )
            else:
                # 直接执行工具
                result = await self.execute_tool(action)
                yield result

    def _should_delegate(self, action: dict) -> bool:
        """判断是否需要委派"""
        # 复杂分析任务、长时间运行的任务委派给子代理
        delegate_tools = {"run_backtest", "deep_analysis", "generate_report"}
        return action.get("tool") in delegate_tools

    def _get_subagent_type(self, action: dict) -> SubagentType:
        """获取子代理类型"""
        tool = action.get("tool")
        mapping = {
            "run_backtest": SubagentType.BACKTEST,
            "deep_analysis": SubagentType.RESEARCH,
            "generate_report": SubagentType.REPORT,
        }
        return mapping.get(tool, SubagentType.RESEARCH)
```

---

### 3.6 Celery 桥接 (课程 09 延伸)

```python
# nanobot/agent/tools/celery_bridge.py 新增
import asyncio
from typing import Optional
from datetime import datetime
import httpx

class CeleryBridge:
    """Celery 任务桥接器"""

    def __init__(self, quant_api_url: str, webhook_base_url: str):
        self.quant_api_url = quant_api_url
        self.webhook_base_url = webhook_base_url
        self.pending_tasks: dict[str, asyncio.Event] = {}
        self.task_results: dict[str, dict] = {}

    async def submit_backtest(
        self,
        strategy: dict,
        symbols: list[str],
        start_date: str,
        end_date: str,
        session_key: str,
    ) -> dict:
        """提交回测任务"""

        # 1. 调用 quant_system API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.quant_api_url}/api/tasks/submit",
                json={
                    "task_name": "run_backtest",
                    "params": {
                        "strategy": strategy,
                        "symbols": symbols,
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                    "webhook_url": f"{self.webhook_base_url}/ai/webhook/task_complete",
                    "session_key": session_key,
                }
            )

        task_id = response.json()["task_id"]

        # 2. 创建等待事件
        event = asyncio.Event()
        self.pending_tasks[task_id] = event

        # 3. 返回任务状态（不阻塞）
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "回测任务已提交，请稍候...",
        }

    async def wait_for_result(self, task_id: str, timeout: float = 300.0) -> Optional[dict]:
        """等待任务结果"""
        if task_id not in self.pending_tasks:
            return None

        event = self.pending_tasks[task_id]
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self.task_results.get(task_id)
        except asyncio.TimeoutError:
            return {"status": "timeout", "task_id": task_id}
        finally:
            del self.pending_tasks[task_id]
            if task_id in self.task_results:
                del self.task_results[task_id]

    async def handle_webhook(self, task_id: str, result: dict):
        """处理 Celery 完成回调"""
        if task_id in self.pending_tasks:
            self.task_results[task_id] = result
            self.pending_tasks[task_id].set()

            # 可选：通过 WebSocket 推送结果
            await self._push_result(result)


# 注册为工具
@registry.register("run_backtest", level=ToolLevel.ANALYSIS)
async def run_backtest_tool(
    strategy: dict,
    symbols: list[str],
    start_date: str,
    end_date: str,
    context: dict,
) -> dict:
    """运行回测 - 异步任务"""
    bridge = get_celery_bridge()

    # 提交任务
    result = await bridge.submit_backtest(
        strategy=strategy,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        session_key=context["session_key"],
    )

    # 如果用户选择等待
    if context.get("wait_for_result"):
        final_result = await bridge.wait_for_result(result["task_id"])
        return final_result or result

    return result
```

---

### 3.7 进化记忆系统 (课程 13)

```python
# nanobot/memory/evolutionary.py 新增
from typing import list
from dataclasses import dataclass
from datetime import datetime

@dataclass
class StrategyMemory:
    """策略记忆"""
    id: int
    user_id: int
    conversation_id: int
    strategy_name: str
    strategy_type: str
    summary: str
    pros: list[str]
    cons: list[str]
    performance_metrics: dict
    lessons_learned: str
    created_at: datetime

class EvolutionaryMemory:
    """进化记忆系统 - 课程 13 延伸"""

    def __init__(self, db_client):
        self.db = db_client

    async def save_reflection(self, reflection: Reflection, session_key: str):
        """保存反思结果"""
        user_id = self._extract_user_id(session_key)

        # 提取策略信息
        strategy_info = self._extract_strategy_info(reflection)

        if strategy_info:
            await self.db.execute("""
                INSERT INTO strategy_memory (
                    user_id, conversation_id, strategy_name, strategy_type,
                    summary, pros, cons, performance_metrics, lessons_learned
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                reflection.conversation_id,
                strategy_info.name,
                strategy_info.type,
                reflection.strategy_summary,
                reflection.what_worked,
                reflection.what_failed,
                reflection.performance_metrics,
                reflection.lessons_learned,
            ))

    async def get_relevant_memories(self, user_id: int, limit: int = 3) -> list[StrategyMemory]:
        """获取相关记忆 - 注入到 System Prompt"""
        memories = await self.db.fetch_all("""
            SELECT * FROM strategy_memory
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))

        return [StrategyMemory(**m) for m in memories]

    def build_memory_prompt(self, memories: list[StrategyMemory]) -> str:
        """构建记忆提示"""
        if not memories:
            return ""

        prompt = "## 你的历史策略经验\n\n"
        for i, mem in enumerate(memories, 1):
            prompt += f"### 策略 {i}: {mem.strategy_name}\n"
            prompt += f"- 类型: {mem.strategy_type}\n"
            prompt += f"- 摘要: {mem.summary}\n"
            prompt += f"- 成功经验: {', '.join(mem.pros)}\n"
            prompt += f"- 失败教训: {', '.join(mem.cons)}\n"
            prompt += f"- 关键指标: {mem.performance_metrics}\n\n"

        prompt += "请参考以上经验，避免重复犯错，发扬成功做法。\n"
        return prompt


# 在 AgentLoop 中使用
class AgentLoop:
    def __init__(self, ...):
        self.memory = EvolutionaryMemory(db_client)

    async def observe(self, user_input: str, session_key: str) -> dict:
        context = {...}

        # 加载进化记忆
        user_id = self._extract_user_id(session_key)
        memories = await self.memory.get_relevant_memories(user_id)
        context["evolutionary_memory"] = self.memory.build_memory_prompt(memories)

        return context
```

---

## 四、前端集成

### 4.1 Vue 3 AI 组件

```vue
<!-- quant_frontend_naive/src/components/AiAssistant.vue -->
<template>
  <n-drawer v-model:show="visible" :width="500" placement="right">
    <n-drawer-content title="AI 投研助手" closable>

      <!-- 消息列表 -->
      <div class="message-container" ref="messageContainer">
        <div v-for="msg in messages" :key="msg.id" :class="['message', msg.role]">

          <!-- Thinking 阶段显示 -->
          <div v-if="msg.phase === 'think'" class="thought-panel">
            <n-alert type="info" title="AI 分析中">
              <n-spin v-if="msg.thinking" />
              <div v-html="renderMarkdown(msg.thought)"></div>
            </n-alert>

            <!-- 需要审批 -->
            <n-alert v-if="msg.requires_approval" type="warning" title="需要确认">
              <div v-html="renderMarkdown(msg.approval_reason)"></div>
              <n-space class="approval-buttons">
                <n-button type="success" @click="approveAction(msg)">
                  确认执行
                </n-button>
                <n-button type="error" @click="rejectAction(msg)">
                  取消
                </n-button>
              </n-space>
            </n-alert>
          </div>

          <!-- 普通消息 -->
          <div v-else class="message-content">
            <div v-html="renderMarkdown(msg.content)"></div>

            <!-- 工具调用显示 -->
            <div v-if="msg.tool_calls" class="tool-calls">
              <n-collapse>
                <n-collapse-item
                  v-for="tool in msg.tool_calls"
                  :key="tool.id"
                  :name="tool.id"
                >
                  <template #header>
                    <n-tag :type="tool.status === 'success' ? 'success' : 'warning'">
                      {{ tool.name }}
                    </n-tag>
                  </template>
                  <n-code :code="JSON.stringify(tool, null, 2)" language="json" />
                </n-collapse-item>
              </n-collapse>
            </div>

            <!-- 子代理任务 -->
            <div v-if="msg.subagent_task" class="subagent-panel">
              <n-progress
                type="line"
                :percentage="msg.subagent_progress || 0"
                :status="msg.subagent_status"
              />
              <span>{{ msg.subagent_summary }}</span>
            </div>
          </div>
        </div>

        <!-- 加载指示器 -->
        <div v-if="isLoading" class="loading-indicator">
          <n-spin size="small" />
          <span>{{ loadingText }}</span>
        </div>
      </div>

      <!-- 输入区域 -->
      <template #footer>
        <n-space vertical>
          <n-input
            v-model:value="inputText"
            type="textarea"
            placeholder="输入消息... (Ctrl+Enter 发送)"
            :autosize="{ minRows: 2, maxRows: 6 }"
            @keydown.enter.ctrl="sendMessage"
          />
          <n-space justify="end">
            <n-button type="primary" @click="sendMessage" :loading="isLoading">
              发送
            </n-button>
          </n-space>
        </n-space>
      </template>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { marked } from 'marked'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  phase?: 'observe' | 'think' | 'act' | 'reflect'
  thought?: string
  requires_approval?: boolean
  approval_reason?: string
  tool_calls?: ToolCall[]
  subagent_task?: boolean
  subagent_progress?: number
  subagent_status?: 'default' | 'success' | 'error'
  subagent_summary?: string
}

const visible = defineModel<boolean>('visible')
const messages = ref<Message[]>([])
const inputText = ref('')
const isLoading = ref(false)
const loadingText = ref('AI 正在思考...')

const { connect, disconnect, send, subscribe } = useWebSocket('/ws/ai')

// 发送消息
const sendMessage = async () => {
  if (!inputText.value.trim() || isLoading.value) return

  messages.value.push({
    id: `user-${Date.now()}`,
    role: 'user',
    content: inputText.value,
  })

  send({ type: 'chat', content: inputText.value })
  inputText.value = ''
  isLoading.value = true
  loadingText.value = 'AI 正在思考...'
}

// 处理 WebSocket 消息
subscribe((data) => {
  switch (data.type) {
    case 'phase':
      // 阶段变化
      loadingText.value = getPhaseText(data.phase)
      break

    case 'think':
      // Thinking 阶段
      messages.value.push({
        id: `think-${Date.now()}`,
        role: 'assistant',
        phase: 'think',
        thought: data.thought,
        requires_approval: data.requires_approval,
        approval_reason: data.approval_reason,
      })
      isLoading.value = false
      break

    case 'stream':
      // 流式内容
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg?.role === 'assistant' && !lastMsg.phase) {
        lastMsg.content += data.content
      } else {
        messages.value.push({
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: data.content,
        })
      }
      break

    case 'tool_call':
      // 工具调用
      const msg = messages.value[messages.value.length - 1]
      if (msg) {
        msg.tool_calls = msg.tool_calls || []
        msg.tool_calls.push(data.tool_call)
      }
      break

    case 'subagent':
      // 子代理任务
      messages.value.push({
        id: `subagent-${Date.now()}`,
        role: 'assistant',
        content: '',
        subagent_task: true,
        subagent_progress: 0,
        subagent_status: 'default',
        subagent_summary: data.summary,
      })
      break

    case 'complete':
      isLoading.value = false
      break
  }

  nextTick(() => scrollToBottom())
})

// 审批操作
const approveAction = async (msg: Message) => {
  send({
    type: 'approval',
    request_id: msg.id,
    approved: true,
  })
  msg.requires_approval = false
  isLoading.value = true
  loadingText.value = '正在执行...'
}

const rejectAction = async (msg: Message) => {
  send({
    type: 'approval',
    request_id: msg.id,
    approved: false,
  })
  msg.requires_approval = false
}

// Markdown 渲染
const renderMarkdown = (content: string) => {
  return marked(content || '')
}

// 阶段文本
const getPhaseText = (phase: string) => {
  const texts = {
    observe: '正在收集信息...',
    think: '正在分析思考...',
    act: '正在执行操作...',
    reflect: '正在总结反思...',
  }
  return texts[phase] || '处理中...'
}

// 滚动到底部
const scrollToBottom = () => {
  const container = document.querySelector('.message-container')
  if (container) {
    container.scrollTop = container.scrollHeight
  }
}

onMounted(() => connect())
onUnmounted(() => disconnect())
</script>
```

---

## 五、数据库设计

```sql
-- AI 会话表
CREATE TABLE ai_conversations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    session_key VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_session (user_id, session_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- AI 消息表（支持阶段标记）
CREATE TABLE ai_messages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL,
    role ENUM('user', 'assistant', 'system') NOT NULL,
    phase ENUM('observe', 'think', 'act', 'reflect'),
    content TEXT NOT NULL,
    thought TEXT,
    tool_calls JSON,
    requires_approval BOOLEAN DEFAULT FALSE,
    tokens_used INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conversation (conversation_id),
    FOREIGN KEY (conversation_id) REFERENCES ai_conversations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 审批请求表
CREATE TABLE approval_requests (
    id VARCHAR(36) PRIMARY KEY,
    user_id BIGINT NOT NULL,
    session_key VARCHAR(255) NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    params JSON NOT NULL,
    thought TEXT,
    status ENUM('pending', 'approved', 'rejected', 'expired') DEFAULT 'pending',
    approved_by BIGINT,
    signature VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    INDEX idx_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 策略进化记忆表
CREATE TABLE strategy_memory (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    conversation_id BIGINT NOT NULL,
    strategy_name VARCHAR(255),
    strategy_type VARCHAR(50),
    summary TEXT NOT NULL,
    pros TEXT,
    cons TEXT,
    performance_metrics JSON,
    lessons_learned TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    FOREIGN KEY (conversation_id) REFERENCES ai_conversations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 审计日志表
CREATE TABLE audit_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    request_id VARCHAR(36) NOT NULL,
    user_id BIGINT,
    action VARCHAR(100) NOT NULL,
    tool_name VARCHAR(100),
    params JSON,
    thought_process TEXT,
    result_status VARCHAR(20),
    ip_address VARCHAR(45),
    duration_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_action (user_id, action),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 六、开发里程碑

| 阶段 | 课程章节 | 内容 | 时间 |
|------|----------|------|------|
| Phase 1 | 02-04 | Main Loop 重写、Thinking 阶段剥离 | Week 1-2 |
| Phase 2 | 05-08 | Tool Registry、并发执行 | Week 3 |
| Phase 3 | 10-14 | Context Compaction、Error Recovery | Week 4 |
| Phase 4 | 15-16 | Middleware 拦截、人工审批 | Week 5-6 |
| Phase 5 | 17 | Subagent 委派 | Week 7 |
| Phase 6 | 09, 13 | Celery 桥接、进化记忆 | Week 8 |
| Phase 7 | - | 前端集成、测试 | Week 9-10 |

---

**文档版本**: v2.0
**创建日期**: 2026-05-10
**参考课程**: 《从 0 开始构建 Agent Harness》
