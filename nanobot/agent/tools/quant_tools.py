"""量化平台工具集

提供股票数据查询、回测、交易等功能的工具。
"""
from typing import Any

import httpx
from loguru import logger

from nanobot.agent.tools.ask import AskUserInterrupt
from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import (
    ArraySchema,
    IntegerSchema,
    NumberSchema,
    StringSchema,
    tool_parameters_schema,
)

# 量化平台 API 地址
QUANT_API_URL = "http://host.docker.internal:8001"


def get_quant_api_url() -> str:
    """获取量化平台 API URL（从配置读取）"""
    try:
        from nanobot.config import get_config
        config = get_config()
        return config.agents.defaults.quant_system_url
    except Exception:
        return QUANT_API_URL


class _QuantTool(Tool):
    """量化工具基类"""

    def __init__(self, api_url: str | None = None):
        self._api_url = api_url or get_quant_api_url()

    @property
    def read_only(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# get_stock_price - 获取股票实时价格
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        symbol=StringSchema("股票代码，如 sh.600519（茅台）、sz.000001（平安银行）"),
        required=["symbol"],
    )
)
class GetStockPriceTool(_QuantTool):
    """获取股票实时价格"""

    @property
    def name(self) -> str:
        return "get_stock_price"

    @property
    def description(self) -> str:
        return "获取股票实时价格，包括当前价、涨跌幅等信息"

    async def execute(self, symbol: str | None = None, **kwargs: Any) -> Any:
        if not symbol:
            return {"error": "缺少股票代码"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self._api_url}/api/market/realtime/{symbol}")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"get_stock_price error: {e}")
                return {"error": str(e), "symbol": symbol}


# ---------------------------------------------------------------------------
# get_stock_info - 获取股票基本信息
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        symbol=StringSchema("股票代码，如 sh.600519"),
        required=["symbol"],
    )
)
class GetStockInfoTool(_QuantTool):
    """获取股票基本信息"""

    @property
    def name(self) -> str:
        return "get_stock_info"

    @property
    def description(self) -> str:
        return "获取股票基本信息，包括名称、行业、市值等"

    async def execute(self, symbol: str | None = None, **kwargs: Any) -> Any:
        if not symbol:
            return {"error": "缺少股票代码"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self._api_url}/data/stocks/{symbol}")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"get_stock_info error: {e}")
                return {"error": str(e), "symbol": symbol}


# ---------------------------------------------------------------------------
# get_kline_data - 获取K线数据
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        symbol=StringSchema("股票代码，如 sh.600519"),
        period=StringSchema("周期，可选 daily(日线)、weekly(周线)、monthly(月线)"),
        limit=IntegerSchema(60, description="返回条数，默认60条", minimum=1, maximum=500),
        required=["symbol"],
    )
)
class GetKlineDataTool(_QuantTool):
    """获取股票K线数据"""

    @property
    def name(self) -> str:
        return "get_kline_data"

    @property
    def description(self) -> str:
        return "获取股票K线数据，包含开高低收、成交量等"

    async def execute(
        self, symbol: str | None = None, period: str = "daily", limit: int = 60, **kwargs: Any
    ) -> Any:
        if not symbol:
            return {"error": "缺少股票代码"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self._api_url}/data/history/{symbol}", params={"limit": limit}
                )
                response.raise_for_status()
                data = response.json()
                return {"symbol": symbol, "period": period, "data": data.get("data", [])[:limit]}
            except httpx.HTTPError as e:
                logger.error(f"get_kline_data error: {e}")
                return {"error": str(e), "symbol": symbol}


# ---------------------------------------------------------------------------
# search_stocks - 搜索股票
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        keyword=StringSchema("搜索关键词，可以是股票代码或名称"),
        limit=IntegerSchema(10, description="返回数量限制", minimum=1, maximum=50),
        required=["keyword"],
    )
)
class SearchStocksTool(_QuantTool):
    """搜索股票"""

    @property
    def name(self) -> str:
        return "search_stocks"

    @property
    def description(self) -> str:
        return "根据关键词搜索股票，返回匹配的股票列表"

    async def execute(self, keyword: str | None = None, limit: int = 10, **kwargs: Any) -> Any:
        if not keyword:
            return {"error": "缺少搜索关键词"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self._api_url}/data/stocks/search",
                    params={"keyword": keyword, "limit": limit},
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"search_stocks error: {e}")
                return {"error": str(e), "keyword": keyword}


# ---------------------------------------------------------------------------
# get_market_overview - 获取市场概览
# ---------------------------------------------------------------------------


@tool_parameters(tool_parameters_schema())
class GetMarketOverviewTool(_QuantTool):
    """获取市场概览"""

    @property
    def name(self) -> str:
        return "get_market_overview"

    @property
    def description(self) -> str:
        return "获取市场整体数据，包括涨跌分布、板块表现等"

    async def execute(self, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self._api_url}/data/stats")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"get_market_overview error: {e}")
                return {"error": str(e)}


# ---------------------------------------------------------------------------
# get_market_sentiment - 获取市场情绪
# ---------------------------------------------------------------------------


@tool_parameters(tool_parameters_schema())
class GetMarketSentimentTool(_QuantTool):
    """获取市场情绪指标"""

    @property
    def name(self) -> str:
        return "get_market_sentiment"

    @property
    def description(self) -> str:
        return "获取市场情绪数据，包括涨跌停数量、封板率等"

    async def execute(self, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self._api_url}/api/market/sentiment")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"get_market_sentiment error: {e}")
                return {"error": str(e)}


# ---------------------------------------------------------------------------
# run_backtest - 运行回测
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        strategy_code=StringSchema("策略Python代码"),
        symbols=ArraySchema(
            StringSchema("股票代码"),
            description="股票代码列表",
        ),
        start_date=StringSchema("开始日期，格式 YYYY-MM-DD"),
        end_date=StringSchema("结束日期，格式 YYYY-MM-DD"),
        initial_capital=NumberSchema(1000000.0, description="初始资金，默认100万"),
        required=["strategy_code", "symbols", "start_date", "end_date"],
    )
)
class RunBacktestTool(_QuantTool):
    """运行回测任务"""

    @property
    def name(self) -> str:
        return "run_backtest"

    @property
    def description(self) -> str:
        return "运行策略回测任务，返回任务ID用于查询结果"

    @property
    def read_only(self) -> bool:
        return False

    async def execute(
        self,
        strategy_code: str | None = None,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        initial_capital: float = 1000000.0,
        **kwargs: Any,
    ) -> Any:
        if not all([strategy_code, symbols, start_date, end_date]):
            return {"error": "缺少必要参数"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self._api_url}/backtest/run-async",
                    json={
                        "strategy_code": strategy_code,
                        "symbols": symbols,
                        "start_date": start_date,
                        "end_date": end_date,
                        "initial_capital": initial_capital,
                    },
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"run_backtest error: {e}")
                return {"error": str(e)}


# ---------------------------------------------------------------------------
# get_backtest_result - 获取回测结果
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        task_id=StringSchema("回测任务ID"),
        required=["task_id"],
    )
)
class GetBacktestResultTool(_QuantTool):
    """获取回测结果"""

    @property
    def name(self) -> str:
        return "get_backtest_result"

    @property
    def description(self) -> str:
        return "获取回测结果，包括收益率、夏普比率、最大回撤等"

    async def execute(self, task_id: str | None = None, **kwargs: Any) -> Any:
        if not task_id:
            return {"error": "缺少任务ID"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self._api_url}/backtest/result/{task_id}")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"get_backtest_result error: {e}")
                return {"error": str(e), "task_id": task_id}


# ---------------------------------------------------------------------------
# get_positions - 获取持仓
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        user_id=IntegerSchema(1, description="用户ID，默认为1"),
    )
)
class GetPositionsTool(_QuantTool):
    """获取当前持仓"""

    @property
    def name(self) -> str:
        return "get_positions"

    @property
    def description(self) -> str:
        return "获取当前持仓列表，包括股票代码、数量、成本、盈亏等"

    async def execute(self, user_id: int = 1, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self._api_url}/api/market/positions/{user_id}")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"get_positions error: {e}")
                return {"error": str(e), "user_id": user_id}


# ---------------------------------------------------------------------------
# get_trading_signals - 获取交易信号
# ---------------------------------------------------------------------------


@tool_parameters(tool_parameters_schema())
class GetTradingSignalsTool(_QuantTool):
    """获取交易信号"""

    @property
    def name(self) -> str:
        return "get_trading_signals"

    @property
    def description(self) -> str:
        return "获取当前的交易信号列表"

    async def execute(self, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self._api_url}/trading/signals")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"get_trading_signals error: {e}")
                return {"error": str(e)}


# ---------------------------------------------------------------------------
# get_watchlist - 获取自选股
# ---------------------------------------------------------------------------


@tool_parameters(tool_parameters_schema())
class GetWatchlistTool(_QuantTool):
    """获取自选股列表"""

    @property
    def name(self) -> str:
        return "get_watchlist"

    @property
    def description(self) -> str:
        return "获取自选股列表，包括股票代码、名称、最新价等"

    async def execute(self, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self._api_url}/api/watchlist")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"get_watchlist error: {e}")
                return {"error": str(e)}


# ---------------------------------------------------------------------------
# add_to_watchlist - 添加自选股
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        symbol=StringSchema("股票代码，如 sh.600519"),
        required=["symbol"],
    )
)
class AddToWatchlistTool(_QuantTool):
    """添加股票到自选股"""

    @property
    def name(self) -> str:
        return "add_to_watchlist"

    @property
    def description(self) -> str:
        return "添加股票到自选股列表"

    @property
    def read_only(self) -> bool:
        return False

    async def execute(self, symbol: str | None = None, **kwargs: Any) -> Any:
        if not symbol:
            return {"error": "缺少股票代码"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self._api_url}/api/watchlist", json={"symbol": symbol}
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"add_to_watchlist error: {e}")
                return {"error": str(e), "symbol": symbol}


# ---------------------------------------------------------------------------
# execute_trade - 执行交易（Mock）
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        symbol=StringSchema("股票代码，如 sh.600519"),
        action=StringSchema("交易方向，buy 或 sell"),
        quantity=IntegerSchema(100, description="交易数量（股）", minimum=1),
        price=NumberSchema(None, description="交易价格，None 表示市价"),
        required=["symbol", "action", "quantity"],
    )
)
class ExecuteTradeTool(_QuantTool):
    """执行交易（当前为 Mock 模式）"""

    @property
    def name(self) -> str:
        return "execute_trade"

    @property
    def description(self) -> str:
        return (
            "执行交易操作。"
            "注意：此操作需要人工确认后才会执行。"
        )

    @property
    def read_only(self) -> bool:
        return False

    async def execute(
        self,
        symbol: str | None = None,
        action: str | None = None,
        quantity: int = 100,
        price: float | None = None,
        **kwargs: Any,
    ) -> Any:
        if not symbol or not action:
            return {"error": "缺少必要参数"}

        # 构建确认消息
        action_text = "买入" if action == "buy" else "卖出"
        price_text = f"价格 {price}" if price else "市价"
        question = (
            f"⚠️ 交易确认请求\n\n"
            f"操作: {action_text} {symbol}\n"
            f"数量: {quantity} 股\n"
            f"价格: {price_text}\n\n"
            f"请确认是否执行此交易？"
        )

        # 抛出中断，等待用户确认
        raise AskUserInterrupt(
            question=question,
            options=["确认执行", "取消"]
        )


# ---------------------------------------------------------------------------
# get_ene_stocks - ENE轨道选股
# ---------------------------------------------------------------------------


@tool_parameters(tool_parameters_schema())
class GetEneStocksTool(_QuantTool):
    """获取ENE轨道选股结果"""

    @property
    def name(self) -> str:
        return "get_ene_stocks"

    @property
    def description(self) -> str:
        return "获取ENE轨道选股结果。ENE轨道是一种技术分析指标，用于判断股价的超买超卖状态。"

    async def execute(self, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self._api_url}/data/ene-select/daily")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"get_ene_stocks error: {e}")
                return {"error": str(e)}


# ---------------------------------------------------------------------------
# analyze_strategy_natural_language - 自然语言生成策略
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        strategy_description=StringSchema("策略的自然语言描述"),
        required=["strategy_description"],
    )
)
class AnalyzeStrategyNaturalLanguageTool(_QuantTool):
    """用自然语言描述策略，AI生成策略代码"""

    @property
    def name(self) -> str:
        return "analyze_strategy_natural_language"

    @property
    def description(self) -> str:
        return "用自然语言描述策略，AI生成策略代码和分析"

    async def execute(self, strategy_description: str | None = None, **kwargs: Any) -> Any:
        if not strategy_description:
            return {"error": "缺少策略描述"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self._api_url}/api/ai/strategy/from-natural-language",
                    json={"description": strategy_description},
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"analyze_strategy_natural_language error: {e}")
                return {"error": str(e)}


# ---------------------------------------------------------------------------
# 工具类定义
# ---------------------------------------------------------------------------
