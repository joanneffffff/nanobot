"""股票分析工具集

调用 langgraph_stock_agent 微服务 API (端口 8002)
提供股票深度分析、K线查询、筛选等功能。

意图识别在微服务内部自动处理，nanobot 只需调用 analyze_stock 即可。
"""
from typing import Any

import httpx
from loguru import logger

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import (
    IntegerSchema,
    StringSchema,
    tool_parameters_schema,
)

# 默认股票分析服务 API 地址（可通过配置覆盖）
STOCK_AGENT_API_URL = "http://host.docker.internal:8002"


def get_stock_agent_url() -> str:
    """获取股票分析服务 URL（从配置读取）"""
    try:
        from nanobot.config import get_config
        config = get_config()
        return config.agents.defaults.stock_agent_url
    except Exception:
        return STOCK_AGENT_API_URL


class _StockAgentTool(Tool):
    """股票分析工具基类"""

    def __init__(self, api_url: str | None = None):
        self._api_url = api_url or get_stock_agent_url()

    @property
    def read_only(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# analyze_stock - 股票深度分析（统一入口，自动处理意图识别）
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        query=StringSchema(
            "用户的股票相关问题。支持多种类型：\n"
            "- 股票分析：'分析贵州茅台的走势'、'宁德时代值得投资吗'\n"
            "- 简单查询：'茅台今天多少钱'、'600519的K线'\n"
            "- 概念分析：'AI概念怎么样'、'新能源板块龙头'\n"
            "- 行业分析：'白酒行业表现如何'\n"
            "- 财报分析：'茅台财报怎么样'\n"
            "- 股票筛选：'筛选涨幅超过5%的股票'\n"
            "- 多轮对话：'它的K线呢'、'这些股票的行业'"
        ),
        user_id=StringSchema("用户ID，默认为 default"),
        session_id=StringSchema("会话ID，用于多轮对话，可选"),
    )
)
class AnalyzeStockTool(_StockAgentTool):
    """股票分析统一入口。

    自动识别用户意图并路由到对应的分析流程：
    - stock_analysis: 深度分析技术走势、基本面、投资价值
    - stock_query: 快速查询价格、K线数据
    - concept_analysis: 概念板块分析
    - industry_analysis: 行业分析
    - financial_analysis: 财报分析
    - tool_call: 股票筛选

    支持多轮对话，会根据上下文自动改写查询。
    """

    @property
    def name(self) -> str:
        return "analyze_stock"

    @property
    def description(self) -> str:
        return (
            "股票分析统一入口。自动识别用户意图，支持：\n"
            "1. 股票深度分析：技术走势、基本面、投资建议\n"
            "2. 简单查询：价格、K线、成交量\n"
            "3. 概念/行业分析：板块走势、龙头股\n"
            "4. 财报分析：营收、利润、财务指标\n"
            "5. 股票筛选：按涨幅、市值、成交额等条件筛选\n"
            "6. 多轮对话：根据上下文理解代词引用"
        )

    async def execute(
        self,
        query: str | None = None,
        user_id: str = "default",
        session_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if not query:
            return {"error": "缺少分析请求"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self._api_url}/api/v2/analyze",
                    json={
                        "query": query,
                        "user_id": user_id,
                        "session_id": session_id,
                    },
                )
                response.raise_for_status()
                data = response.json()

                # 提取关键信息
                result = {
                    "status": data.get("status"),
                    "session_id": data.get("session_id"),
                    "intent": data.get("intent", {}),
                }

                if "data" in data:
                    result["response"] = data["data"].get("final_response", "")
                    result["stock_codes"] = data["data"].get("stock_codes", [])
                    result["concepts"] = data["data"].get("concepts", [])
                    result["chart_data"] = data["data"].get("chart_data_payload", {})

                return result

            except httpx.HTTPError as e:
                logger.error(f"analyze_stock error: {e}")
                return {"error": str(e), "query": query}


# ---------------------------------------------------------------------------
# get_stock_kline - 获取K线数据
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        ticker=StringSchema("股票代码，如 sh.600519"),
        limit=IntegerSchema(60, description="返回条数，默认60条", minimum=1, maximum=500),
    )
)
class GetStockKlineTool(_StockAgentTool):
    """获取股票K线数据"""

    @property
    def name(self) -> str:
        return "get_stock_kline"

    @property
    def description(self) -> str:
        return "获取股票K线数据，包含开高低收、成交量等"

    async def execute(self, ticker: str | None = None, limit: int = 60, **kwargs: Any) -> Any:
        if not ticker:
            return {"error": "缺少股票代码"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self._api_url}/api/v2/kline",
                    json={"ticker": ticker, "limit": limit},
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPError as e:
                logger.error(f"get_stock_kline error: {e}")
                return {"error": str(e), "ticker": ticker}


# ---------------------------------------------------------------------------
# filter_stocks - 股票筛选
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        condition=StringSchema("筛选条件描述，如 '涨幅大于5%且成交额过亿'"),
        limit=IntegerSchema(20, description="返回数量限制", minimum=1, maximum=100),
    )
)
class FilterStocksTool(_StockAgentTool):
    """股票筛选"""

    @property
    def name(self) -> str:
        return "filter_stocks"

    @property
    def description(self) -> str:
        return (
            "根据条件筛选股票。"
            "支持涨幅、跌幅、成交额、市值等条件。"
            "如 '涨幅大于5%'、'市值小于50亿'、'成交额过亿'"
        )

    async def execute(
        self, condition: str | None = None, limit: int = 20, **kwargs: Any
    ) -> Any:
        if not condition:
            return {"error": "缺少筛选条件"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self._api_url}/api/v2/filter",
                    json={"sql_query": condition, "limit": limit},
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPError as e:
                logger.error(f"filter_stocks error: {e}")
                return {"error": str(e), "condition": condition}


# ---------------------------------------------------------------------------
# analyze_concept - 概念分析
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        concept_name=StringSchema("概念名称，如 AI、新能源、人形机器人"),
    )
)
class AnalyzeConceptTool(_StockAgentTool):
    """概念板块分析"""

    @property
    def name(self) -> str:
        return "analyze_concept"

    @property
    def description(self) -> str:
        return (
            "分析概念板块，包括走势、龙头股、成分股等。"
            "如 '分析AI概念'、'新能源板块怎么样'"
        )

    async def execute(self, concept_name: str | None = None, **kwargs: Any) -> Any:
        if not concept_name:
            return {"error": "缺少概念名称"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self._api_url}/api/v2/concept",
                    json={"concept_name": concept_name},
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPError as e:
                logger.error(f"analyze_concept error: {e}")
                return {"error": str(e), "concept_name": concept_name}


# ---------------------------------------------------------------------------
# get_chart - 获取图表数据
# ---------------------------------------------------------------------------


@tool_parameters(
    tool_parameters_schema(
        chart_id=StringSchema("图表ID"),
    )
)
class GetChartTool(_StockAgentTool):
    """获取图表数据"""

    @property
    def name(self) -> str:
        return "get_chart"

    @property
    def description(self) -> str:
        return "根据图表ID获取图表JSON数据，用于前端渲染"

    async def execute(self, chart_id: str | None = None, **kwargs: Any) -> Any:
        if not chart_id:
            return {"error": "缺少图表ID"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self._api_url}/api/v2/chart/{chart_id}")
                response.raise_for_status()
                return response.json()

            except httpx.HTTPError as e:
                logger.error(f"get_chart error: {e}")
                return {"error": str(e), "chart_id": chart_id}
