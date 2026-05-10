"""工具执行中间件

在工具执行前后插入自定义逻辑，如审批、审计等。
"""
from dataclasses import dataclass
from typing import Any, Callable

from loguru import logger


@dataclass
class ToolExecutionContext:
    """工具执行上下文"""

    tool_name: str
    arguments: dict[str, Any]
    session_key: str
    channel: str
    chat_id: str


@dataclass
class ApprovalRequest:
    """审批请求"""

    tool_name: str
    arguments: dict[str, Any]
    message: str
    options: list[str]


class ApprovalRequiredError(Exception):
    """需要审批时抛出"""

    def __init__(self, request: ApprovalRequest) -> None:
        self.request = request
        super().__init__(request.message)


# 需要审批的工具配置
APPROVAL_CONFIG: dict[str, dict[str, Any]] = {
    "execute_trade": {
        "message_template": "⚠️ 交易确认请求\n\n操作: {action} {symbol}\n数量: {quantity} 股\n价格: {price_text}\n\n请确认是否执行此交易？",
        "options": ["确认执行", "取消"],
        "cancel_response": {"status": "cancelled", "message": "用户取消了交易"},
    },
}


def check_approval_required(tool_name: str, arguments: dict[str, Any]) -> ApprovalRequest | None:
    """检查工具执行是否需要审批

    Args:
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        如果需要审批，返回 ApprovalRequest；否则返回 None
    """
    config = APPROVAL_CONFIG.get(tool_name)
    if not config:
        return None

    # 构建审批消息
    message_template = config.get("message_template", "确认执行 {tool_name}?")
    options = config.get("options", ["确认", "取消"])

    # 替换模板变量
    message = message_template.format(
        tool_name=tool_name,
        **arguments,
        price_text=f"{arguments.get('price')}" if arguments.get("price") else "市价",
    )

    return ApprovalRequest(
        tool_name=tool_name,
        arguments=arguments,
        message=message,
        options=options,
    )


def process_approval_response(
    tool_name: str, arguments: dict[str, Any], response: str
) -> tuple[bool, dict[str, Any]]:
    """处理审批响应

    Args:
        tool_name: 工具名称
        arguments: 工具参数
        response: 用户响应

    Returns:
        (是否批准, 执行结果或取消消息)
    """
    config = APPROVAL_CONFIG.get(tool_name, {})
    cancel_response = config.get("cancel_response", {"status": "cancelled"})

    # 检查用户是否确认
    approved = "确认" in response or response.lower() in ["yes", "ok", "confirm", "是"]

    if not approved:
        return False, cancel_response

    return True, {}


class ToolMiddleware:
    """工具执行中间件基类"""

    async def before_execute(
        self, ctx: ToolExecutionContext
    ) -> tuple[bool, dict[str, Any] | None]:
        """工具执行前调用

        Args:
            ctx: 执行上下文

        Returns:
            (是否继续执行, 如果不继续，返回替代结果)
        """
        return True, None

    async def after_execute(
        self, ctx: ToolExecutionContext, result: dict[str, Any]
    ) -> dict[str, Any]:
        """工具执行后调用

        Args:
            ctx: 执行上下文
            result: 执行结果

        Returns:
            可能修改后的结果
        """
        return result


class ApprovalMiddleware(ToolMiddleware):
    """审批中间件

    在执行需要审批的工具前，检查是否已获得批准。
    """

    def __init__(self) -> None:
        # 存储已批准的操作 (session_key, tool_name, args_hash) -> True
        self._approved: set[tuple[str, str, int]] = set()

    def _make_key(self, ctx: ToolExecutionContext) -> tuple[str, str, int]:
        """生成唯一键"""
        import hashlib

        args_str = str(sorted(ctx.arguments.items()))
        args_hash = int(hashlib.md5(args_str.encode()).hexdigest()[:8], 16)
        return (ctx.session_key, ctx.tool_name, args_hash)

    def approve(self, ctx: ToolExecutionContext) -> None:
        """批准操作"""
        key = self._make_key(ctx)
        self._approved.add(key)
        logger.info(f"Approved: {ctx.tool_name} for {ctx.session_key}")

    def is_approved(self, ctx: ToolExecutionContext) -> bool:
        """检查是否已批准"""
        key = self._make_key(ctx)
        return key in self._approved

    def clear_approval(self, ctx: ToolExecutionContext) -> None:
        """清除批准"""
        key = self._make_key(ctx)
        self._approved.discard(key)

    async def before_execute(
        self, ctx: ToolExecutionContext
    ) -> tuple[bool, dict[str, Any] | None]:
        """检查是否需要审批"""
        request = check_approval_required(ctx.tool_name, ctx.arguments)

        if not request:
            return True, None

        # 检查是否已批准
        if self.is_approved(ctx):
            self.clear_approval(ctx)  # 使用后清除
            return True, None

        # 需要审批但未批准
        raise ApprovalRequiredError(request)


class AuditMiddleware(ToolMiddleware):
    """审计中间件

    记录工具执行日志。
    """

    async def before_execute(
        self, ctx: ToolExecutionContext
    ) -> tuple[bool, dict[str, Any] | None]:
        """记录执行前日志"""
        logger.info(
            f"[Audit] Tool call: {ctx.tool_name}({ctx.arguments}) "
            f"session={ctx.session_key} channel={ctx.channel}"
        )
        return True, None

    async def after_execute(
        self, ctx: ToolExecutionContext, result: dict[str, Any]
    ) -> dict[str, Any]:
        """记录执行后日志"""
        status = "error" if "error" in result else "success"
        logger.info(f"[Audit] Tool result: {ctx.tool_name} -> {status}")
        return result
