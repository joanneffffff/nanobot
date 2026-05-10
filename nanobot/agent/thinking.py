"""独立思考阶段实现

在执行操作前，先进行独立思考分析，评估风险。
对于高风险操作（如交易），需要人工确认。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class ActionType(Enum):
    """操作类型"""

    READ = "read"  # 只读操作（查询数据）
    ANALYSIS = "analysis"  # 分析操作（回测、策略分析）
    TRADE = "trade"  # 交易操作（买入、卖出）
    CONFIG = "config"  # 配置操作（修改设置）


@dataclass
class Thought:
    """思考结果"""

    analysis: str  # 分析内容
    proposed_actions: list[dict[str, Any]] = field(default_factory=list)  # 拟执行动作
    risk_assessment: str = ""  # 风险评估
    confidence: float = 0.8  # 置信度 0-1
    requires_approval: bool = False  # 是否需要人工确认
    approval_reason: str | None = None  # 需要确认的原因
    phase: str = "think"  # 阶段标识


# 需要审批的工具
APPROVAL_REQUIRED_TOOLS = {
    "execute_trade",
    "add_to_watchlist",  # 可选：添加自选股也可以需要确认
}

# 高风险工具（总是需要审批）
HIGH_RISK_TOOLS = {
    "execute_trade",
}

# 只读工具（不需要审批）
READ_ONLY_TOOLS = {
    "get_stock_price",
    "get_stock_info",
    "get_kline_data",
    "search_stocks",
    "get_market_overview",
    "get_market_sentiment",
    "get_backtest_result",
    "get_positions",
    "get_trading_signals",
    "get_watchlist",
    "get_ene_stocks",
}


class ThinkingEngine:
    """独立思考引擎

    在执行操作前进行独立思考，不调用任何工具。
    分析用户需求，评估风险，判断是否需要人工确认。
    """

    def __init__(self, confidence_threshold: float = 0.7):
        """
        Args:
            confidence_threshold: 置信度阈值，低于此值需要人工确认
        """
        self.confidence_threshold = confidence_threshold

    def check_approval_required(self, thought: Thought) -> bool:
        """检查是否需要人工确认

        以下情况需要确认：
        1. 涉及高风险工具（交易）
        2. 置信度低于阈值
        3. 明确标记需要确认的操作
        """
        # 检查是否有高风险工具
        for action in thought.proposed_actions:
            tool_name = action.get("tool", "")
            if tool_name in HIGH_RISK_TOOLS:
                thought.approval_reason = f"涉及交易操作: {tool_name}"
                return True

        # 检查置信度
        if thought.confidence < self.confidence_threshold:
            thought.approval_reason = f"置信度较低: {thought.confidence:.2f} < {self.confidence_threshold}"
            return True

        return False

    def get_thinking_system_prompt(self) -> str:
        """获取思考阶段的系统提示"""
        return """你是量化交易分析师。现在进入独立思考阶段。

你的任务：
1. 分析用户需求和市场情况
2. 设计可能的策略或操作方案
3. 评估每个方案的风险和收益
4. 给出建议和置信度

重要：
- 本阶段只能思考，不能执行任何操作
- 对于交易类操作，必须给出详细风险评估
- 涉及实盘交易，必须等待人工确认
- 置信度范围 0-1，低于 0.7 需要人工确认

输出格式（JSON）：
{
  "analysis": "市场分析内容",
  "proposed_actions": [
    {"tool": "工具名", "args": {"参数": "值"}, "reason": "执行原因"}
  ],
  "risk_assessment": "风险评估",
  "confidence": 0.85
}

注意：
- 查询类操作（如获取股价、K线）风险较低
- 分析类操作（如回测）风险中等
- 交易类操作（如买入卖出）风险最高，必须详细评估"""

    def parse_thought_from_response(self, content: str) -> Thought:
        """从 LLM 响应中解析思考结果

        Args:
            content: LLM 响应内容

        Returns:
            Thought 对象
        """
        import json
        import re

        # 尝试从响应中提取 JSON
        thought = Thought(analysis=content)

        # 查找 JSON 块
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                thought.analysis = data.get("analysis", content)
                thought.proposed_actions = data.get("proposed_actions", [])
                thought.risk_assessment = data.get("risk_assessment", "")
                thought.confidence = float(data.get("confidence", 0.8))
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse thought JSON: {e}")

        # 如果没有找到 JSON，尝试直接解析
        if not thought.proposed_actions:
            # 尝试解析整个内容为 JSON
            try:
                data = json.loads(content)
                thought.analysis = data.get("analysis", content)
                thought.proposed_actions = data.get("proposed_actions", [])
                thought.risk_assessment = data.get("risk_assessment", "")
                thought.confidence = float(data.get("confidence", 0.8))
            except (json.JSONDecodeError, ValueError):
                pass

        # 确保置信度在有效范围内
        thought.confidence = max(0.0, min(1.0, thought.confidence))

        # 检查是否需要审批
        thought.requires_approval = self.check_approval_required(thought)

        return thought


def classify_tool_action(tool_name: str) -> ActionType:
    """分类工具操作类型

    Args:
        tool_name: 工具名称

    Returns:
        ActionType 枚举值
    """
    if tool_name in READ_ONLY_TOOLS:
        return ActionType.READ
    elif tool_name in HIGH_RISK_TOOLS:
        return ActionType.TRADE
    elif tool_name == "run_backtest":
        return ActionType.ANALYSIS
    else:
        return ActionType.READ


def should_show_thinking_phase(tool_calls: list[dict[str, Any]]) -> bool:
    """判断是否需要显示思考阶段

    对于简单的查询操作，可以跳过思考阶段直接执行。
    对于复杂操作或交易操作，需要先思考。

    Args:
        tool_calls: 计划执行的工具调用列表

    Returns:
        是否需要显示思考阶段
    """
    if not tool_calls:
        return False

    # 如果有交易操作，必须思考
    for call in tool_calls:
        tool_name = call.get("tool", call.get("name", ""))
        if tool_name in HIGH_RISK_TOOLS:
            return True

    # 如果有多个操作，需要思考
    if len(tool_calls) > 2:
        return True

    # 单个只读操作，可以跳过思考
    for call in tool_calls:
        tool_name = call.get("tool", call.get("name", ""))
        if tool_name not in READ_ONLY_TOOLS:
            return True

    return False
