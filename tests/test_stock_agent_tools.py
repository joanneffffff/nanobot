"""Tests for stock agent tools intent recognition and routing."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from nanobot.agent.tools.stock_agent_tools import (
    AnalyzeStockTool,
    RecognizeIntentTool,
    GetStockKlineTool,
    FilterStocksTool,
    AnalyzeConceptTool,
    RewriteQueryTool,
)


class TestRecognizeIntentTool:
    """Test intent recognition tool."""

    def test_tool_properties(self):
        """Test basic tool properties."""
        tool = RecognizeIntentTool()
        assert tool.name == "recognize_intent"
        assert "意图识别" in tool.description
        assert tool.read_only is True

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
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_missing_query(self):
        """Test with missing query parameter."""
        tool = RecognizeIntentTool()
        result = await tool.execute()
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_http_error(self):
        """Test HTTP error handling."""
        tool = RecognizeIntentTool(api_url="http://test:8002")

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPError("Connection failed")

            result = await tool.execute(query="测试查询")
            assert "error" in result


class TestAnalyzeStockTool:
    """Test stock analysis tool."""

    def test_tool_properties(self):
        """Test basic tool properties."""
        tool = AnalyzeStockTool()
        assert tool.name == "analyze_stock"
        assert "深度分析" in tool.description

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful stock analysis."""
        tool = AnalyzeStockTool(api_url="http://test:8002")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "session_id": "test-session",
            "intent": {"type": "stock_analysis"},
            "data": {
                "final_response": "茅台近期走势...",
                "stock_codes": ["sh.600519"],
                "concepts": ["白酒"],
            },
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(
                query="分析茅台",
                user_id="test_user",
                session_id="test-session"
            )

            assert result["status"] == "success"
            assert "response" in result
            assert result["stock_codes"] == ["sh.600519"]


class TestGetStockKlineTool:
    """Test K-line data retrieval tool."""

    def test_tool_properties(self):
        """Test basic tool properties."""
        tool = GetStockKlineTool()
        assert tool.name == "get_stock_kline"
        assert "K线" in tool.description

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful K-line retrieval."""
        tool = GetStockKlineTool(api_url="http://test:8002")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"date": "2024-01-01", "open": 100, "close": 105},
                {"date": "2024-01-02", "open": 105, "close": 110},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(ticker="sh.600519", limit=60)

            assert "data" in result
            mock_post.assert_called_once()


class TestFilterStocksTool:
    """Test stock filtering tool."""

    def test_tool_properties(self):
        """Test basic tool properties."""
        tool = FilterStocksTool()
        assert tool.name == "filter_stocks"
        assert "筛选" in tool.description

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful stock filtering."""
        tool = FilterStocksTool(api_url="http://test:8002")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "stocks": [
                {"code": "sh.600519", "name": "贵州茅台", "change": 5.2},
                {"code": "sz.000001", "name": "平安银行", "change": 6.1},
            ],
            "total": 2
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(condition="涨幅大于5%", limit=20)

            assert "stocks" in result
            mock_post.assert_called_once()


class TestAnalyzeConceptTool:
    """Test concept analysis tool."""

    def test_tool_properties(self):
        """Test basic tool properties."""
        tool = AnalyzeConceptTool()
        assert tool.name == "analyze_concept"
        assert "概念" in tool.description

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful concept analysis."""
        tool = AnalyzeConceptTool(api_url="http://test:8002")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "concept": "AI",
            "stocks": [
                {"code": "sh.600519", "name": "股票1"},
            ],
            "analysis": "AI概念板块近期..."
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(concept_name="AI")

            assert "concept" in result


class TestRewriteQueryTool:
    """Test query rewriting tool for multi-turn conversations."""

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
            "original_query": "它的K线怎么样"
        }
        mock_response.raise_for_status = MagicMock()

        chat_history = [
            {"role": "user", "content": "茅台今天多少钱"},
            {"role": "assistant", "content": "茅台今天收盘价1800元"},
        ]

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(
                current_query="它的K线怎么样",
                chat_history=chat_history
            )

            assert "rewritten_query" in result


class TestToolIntegration:
    """Test tool integration scenarios."""

    @pytest.mark.asyncio
    async def test_intent_to_analysis_flow(self):
        """Test flow from intent recognition to stock analysis."""
        # Step 1: Recognize intent
        intent_tool = RecognizeIntentTool(api_url="http://test:8002")

        mock_intent_response = MagicMock()
        mock_intent_response.json.return_value = {
            "intent": "stock_analysis",
            "confidence": 0.95,
            "entities": {"stock_code": "sh.600519"},
            "rewritten_query": "分析贵州茅台的走势",
        }
        mock_intent_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_intent_response

            intent_result = await intent_tool.execute(query="茅台走势")

            assert intent_result["intent"] == "stock_analysis"

            # Step 2: Use analysis tool with recognized entity
            analyze_tool = AnalyzeStockTool(api_url="http://test:8002")

            mock_analyze_response = MagicMock()
            mock_analyze_response.json.return_value = {
                "status": "success",
                "data": {"final_response": "分析结果..."},
            }
            mock_analyze_response.raise_for_status = MagicMock()

            mock_post.return_value = mock_analyze_response

            analysis_result = await analyze_tool.execute(
                query=intent_result["rewritten_query"]
            )

            assert analysis_result["status"] == "success"

    @pytest.mark.asyncio
    async def test_multi_turn_conversation_flow(self):
        """Test multi-turn conversation with query rewriting."""
        rewrite_tool = RewriteQueryTool(api_url="http://test:8002")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "rewritten_query": "贵州茅台的K线走势怎么样",
        }
        mock_response.raise_for_status = MagicMock()

        chat_history = [
            {"role": "user", "content": "帮我看看茅台"},
            {"role": "assistant", "content": "好的，茅台是贵州茅台股票..."},
        ]

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await rewrite_tool.execute(
                current_query="它的K线怎么样",
                chat_history=chat_history
            )

            assert "茅台" in result["rewritten_query"]


class TestQuantToolsConfiguration:
    """Test quant tools configuration integration."""

    def test_get_quant_api_url_from_config(self):
        """Test that quant tools read URL from config."""
        from nanobot.agent.tools.quant_tools import get_quant_api_url

        # Should return default when config fails
        url = get_quant_api_url()
        assert url is not None
        assert "8001" in url or "host.docker.internal" in url

    def test_get_stock_agent_url_from_config(self):
        """Test that stock agent tools read URL from config."""
        from nanobot.agent.tools.stock_agent_tools import get_stock_agent_url

        url = get_stock_agent_url()
        assert url is not None
        assert "8002" in url or "host.docker.internal" in url

    def test_tool_initialization_with_custom_url(self):
        """Test tool initialization with custom API URL."""
        custom_url = "http://custom:9000"
        tool = AnalyzeStockTool(api_url=custom_url)
        assert tool._api_url == custom_url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
