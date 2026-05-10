"""Tests for intent recognition tools."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from nanobot.agent.tools.intent_tools import (
    RecognizeIntentTool,
    RouteIntentTool,
    RewriteQueryTool,
    INTENT_TOOLS,
)


class TestRecognizeIntentTool:
    """Test intent recognition tool."""

    def test_tool_properties(self):
        """Test basic tool properties."""
        tool = RecognizeIntentTool()
        assert tool.name == "recognize_intent"
        assert "意图识别" in tool.description
        assert tool.read_only is True

    def test_suggest_tool_mapping(self):
        """Test tool suggestion logic."""
        tool = RecognizeIntentTool()

        # Stock analysis -> analyze_stock
        assert tool._suggest_tool("stock_analysis", {}) == "analyze_stock"

        # Stock query with stock_code -> get_stock_price
        assert tool._suggest_tool("stock_query", {"stock_code": "sh.600519"}) == "get_stock_price"

        # Concept analysis with concept_name -> analyze_concept
        assert tool._suggest_tool("concept_analysis", {"concept_name": "AI"}) == "analyze_concept"

        # Tool call -> filter_stocks
        assert tool._suggest_tool("tool_call", {}) == "filter_stocks"

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful intent recognition."""
        tool = RecognizeIntentTool(api_url="http://test:8002")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "intent": "stock_analysis",
            "confidence": 0.95,
            "entities": {"stock_code": "sh.600519"},
            "rewritten_query": "分析贵州茅台的走势",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(query="茅台走势怎么样")

            assert result["intent"] == "stock_analysis"
            assert result["confidence"] == 0.95
            assert result["suggested_tool"] == "analyze_stock"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_context(self):
        """Test intent recognition with context."""
        tool = RecognizeIntentTool(api_url="http://test:8002")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "intent": "stock_query",
            "confidence": 0.9,
            "entities": {"stock_code": "sh.600519"},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(query="它今天多少钱", context="之前讨论了茅台")

            assert result["intent"] == "stock_query"
            assert result["suggested_tool"] == "get_stock_price"

    @pytest.mark.asyncio
    async def test_execute_missing_query(self):
        """Test with missing query parameter."""
        tool = RecognizeIntentTool()
        result = await tool.execute()
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_http_error(self):
        """Test HTTP error handling with fallback."""
        tool = RecognizeIntentTool(api_url="http://test:8002")

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPError("Connection failed")

            result = await tool.execute(query="测试查询")

            assert "error" in result
            assert result["intent"] == "general_chat"
            assert result["suggested_tool"] == "analyze_stock"


class TestRouteIntentTool:
    """Test intent routing tool."""

    def test_tool_properties(self):
        """Test basic tool properties."""
        tool = RouteIntentTool()
        assert tool.name == "route_intent"
        assert "路由" in tool.description

    def test_endpoint_mapping(self):
        """Test endpoint selection logic."""
        tool = RouteIntentTool()

        # Concept analysis -> /api/v2/concept
        assert tool._get_endpoint("concept_analysis", {"concept_name": "AI"}) == "/api/v2/concept"

        # Stock query with stock_code -> /api/v2/kline
        assert tool._get_endpoint("stock_query", {"stock_code": "sh.600519"}) == "/api/v2/kline"

        # Tool call -> /api/v2/filter
        assert tool._get_endpoint("tool_call", {}) == "/api/v2/filter"

        # Default -> /api/v2/analyze
        assert tool._get_endpoint("stock_analysis", {}) == "/api/v2/analyze"

    def test_params_building(self):
        """Test parameter building logic."""
        tool = RouteIntentTool()

        # Concept analysis
        params = tool._build_params("concept_analysis", "AI概念", {"concept_name": "AI"})
        assert params["concept_name"] == "AI"

        # Stock query
        params = tool._build_params("stock_query", "茅台K线", {"stock_code": "sh.600519"})
        assert params["ticker"] == "sh.600519"
        assert params["limit"] == 60

        # Tool call
        params = tool._build_params("tool_call", "涨幅>5%", {})
        assert params["sql_query"] == "涨幅>5%"
        assert params["limit"] == 20

        # Stock analysis
        params = tool._build_params("stock_analysis", "分析茅台", {})
        assert params["query"] == "分析茅台"

    @pytest.mark.asyncio
    async def test_execute_auto_recognize(self):
        """Test routing with automatic intent recognition."""
        tool = RouteIntentTool(api_url="http://test:8002")

        # Mock recognize response
        mock_recognize_response = MagicMock()
        mock_recognize_response.json.return_value = {
            "intent": "concept_analysis",
            "confidence": 0.9,
            "entities": {"concept_name": "AI"},
            "rewritten_query": "分析AI概念板块",
        }
        mock_recognize_response.raise_for_status = MagicMock()

        # Mock analyze response
        mock_analyze_response = MagicMock()
        mock_analyze_response.json.return_value = {
            "concept": "AI",
            "stocks": [{"code": "sh.600519", "name": "股票1"}],
            "analysis": "AI概念分析结果",
        }
        mock_analyze_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [mock_recognize_response, mock_analyze_response]

            result = await tool.execute(query="AI概念怎么样")

            assert result["concept"] == "AI"
            assert result["routed_intent"] == "concept_analysis"

    @pytest.mark.asyncio
    async def test_execute_with_explicit_intent(self):
        """Test routing with explicit intent."""
        tool = RouteIntentTool(api_url="http://test:8002")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "data": {"final_response": "分析结果"},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(query="分析茅台", intent="stock_analysis")

            assert result["routed_intent"] == "stock_analysis"
            # Should only call once (no recognize step)
            mock_post.assert_called_once()


class TestRewriteQueryTool:
    """Test query rewriting tool."""

    def test_tool_properties(self):
        """Test basic tool properties."""
        tool = RewriteQueryTool()
        assert tool.name == "rewrite_query"
        assert "改写" in tool.description

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful query rewriting."""
        tool = RewriteQueryTool(api_url="http://test:8002")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "rewritten_query": "分析贵州茅台的K线走势",
            "original_query": "它的K线怎么样",
        }
        mock_response.raise_for_status = MagicMock()

        chat_history = '[{"role": "user", "content": "茅台今天多少钱"}, {"role": "assistant", "content": "茅台今天收盘价1800元"}]'

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(
                current_query="它的K线怎么样",
                chat_history=chat_history
            )

            assert "rewritten_query" in result
            assert "茅台" in result["rewritten_query"]

    @pytest.mark.asyncio
    async def test_execute_invalid_json_history(self):
        """Test with invalid JSON chat history."""
        tool = RewriteQueryTool(api_url="http://test:8002")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "rewritten_query": "K线走势怎么样",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            # Invalid JSON should be handled gracefully
            result = await tool.execute(
                current_query="K线走势怎么样",
                chat_history="not valid json"
            )

            assert "rewritten_query" in result


class TestIntentToolsList:
    """Test intent tools registration."""

    def test_tools_list(self):
        """Test that all intent tools are registered."""
        assert len(INTENT_TOOLS) == 3
        tool_names = [t().name for t in INTENT_TOOLS]
        assert "recognize_intent" in tool_names
        assert "route_intent" in tool_names
        assert "rewrite_query" in tool_names

    def test_all_tools_are_tool_subclass(self):
        """Test that all tools inherit from Tool."""
        from nanobot.agent.tools.base import Tool
        for tool_cls in INTENT_TOOLS:
            assert issubclass(tool_cls, Tool)


class TestIntentFlowIntegration:
    """Test complete intent recognition flow."""

    @pytest.mark.asyncio
    async def test_recognize_then_route_flow(self):
        """Test flow: recognize -> route -> analyze."""
        # Step 1: Recognize intent
        recognize_tool = RecognizeIntentTool(api_url="http://test:8002")

        mock_recognize = MagicMock()
        mock_recognize.json.return_value = {
            "intent": "stock_analysis",
            "confidence": 0.95,
            "entities": {"stock_code": "sh.600519"},
            "rewritten_query": "分析贵州茅台的走势",
            "suggested_tool": "analyze_stock",
        }
        mock_recognize.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_recognize

            intent_result = await recognize_tool.execute(query="茅台走势")

            assert intent_result["intent"] == "stock_analysis"
            assert intent_result["suggested_tool"] == "analyze_stock"

    @pytest.mark.asyncio
    async def test_concept_analysis_flow(self):
        """Test concept analysis flow."""
        route_tool = RouteIntentTool(api_url="http://test:8002")

        mock_recognize = MagicMock()
        mock_recognize.json.return_value = {
            "intent": "concept_analysis",
            "entities": {"concept_name": "新能源"},
            "rewritten_query": "分析新能源概念",
        }
        mock_recognize.raise_for_status = MagicMock()

        mock_concept = MagicMock()
        mock_concept.json.return_value = {
            "concept": "新能源",
            "stocks": [{"code": "sh.600519", "name": "股票"}],
        }
        mock_concept.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [mock_recognize, mock_concept]

            result = await route_tool.execute(query="新能源概念怎么样")

            assert result["concept"] == "新能源"
            assert result["routed_intent"] == "concept_analysis"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])