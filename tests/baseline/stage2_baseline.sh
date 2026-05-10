#!/bin/bash
# Stage 2 Baseline Tests
# 验证量化工具集成正常工作

set -e

echo "=== Stage 2 Quant Tools Integration Tests ==="
echo ""

# 1. Gateway Health
echo "1. Gateway Health Check..."
HEALTH=$(curl -s http://127.0.0.1:18790/health)
if [ "$HEALTH" = '{"status":"ok"}' ] || [ "$HEALTH" = '{"status": "ok"}' ]; then
    echo "   ✅ Gateway health OK"
else
    echo "   ❌ Gateway health failed: $HEALTH"
    exit 1
fi

# 2. Quant System Health
echo "2. Quant System Health Check..."
QUANT_HEALTH=$(curl -s http://127.0.0.1:8001/health)
if echo "$QUANT_HEALTH" | grep -q '"status"'; then
    echo "   ✅ Quant system health OK"
else
    echo "   ❌ Quant system health failed"
    exit 1
fi

# 3. Quant Tools Loaded
echo "3. Quant Tools Check..."
TOOL_COUNT=$(docker exec nanobot-gateway python -c "
from nanobot.agent.tools.quant_tools import QUANT_TOOLS
print(len(QUANT_TOOLS))
" 2>/dev/null)
if [ "$TOOL_COUNT" = "15" ]; then
    echo "   ✅ All 15 quant tools loaded"
else
    echo "   ❌ Expected 15 tools, got $TOOL_COUNT"
    exit 1
fi

# 4. Tool Serialization
echo "4. Tool Serialization Check..."
SERIALIZE_OK=$(docker exec nanobot-gateway python -c "
import json
from nanobot.agent.tools.quant_tools import QUANT_TOOLS
from nanobot.agent.tools.registry import ToolRegistry
registry = ToolRegistry()
for t in QUANT_TOOLS:
    registry.register(t())
defs = registry.get_definitions()
try:
    json.dumps(defs)
    print('OK')
except:
    print('FAIL')
" 2>/dev/null)
if [ "$SERIALIZE_OK" = "OK" ]; then
    echo "   ✅ Tool serialization OK"
else
    echo "   ❌ Tool serialization failed"
    exit 1
fi

# 5. Direct Tool Execution
echo "5. Direct Tool Execution Check..."
TOOL_RESULT=$(docker exec nanobot-gateway python -c "
import asyncio
from nanobot.agent.tools.quant_tools import GetMarketSentimentTool

async def test():
    tool = GetMarketSentimentTool()
    result = await tool.execute()
    if 'success' in result and result['success']:
        print('OK')
    else:
        print('FAIL')

asyncio.run(test())
" 2>/dev/null)
if [ "$TOOL_RESULT" = "OK" ]; then
    echo "   ✅ Tool execution OK"
else
    echo "   ❌ Tool execution failed"
    exit 1
fi

# 6. Docker Containers
echo "6. Docker Containers Check..."
GATEWAY=$(docker ps --filter "name=nanobot-gateway" --format "{{.Status}}")
API=$(docker ps --filter "name=nanobot-api" --format "{{.Status}}")
if echo "$GATEWAY" | grep -q "Up"; then
    echo "   ✅ Gateway container: $GATEWAY"
else
    echo "   ❌ Gateway container not running"
    exit 1
fi
if echo "$API" | grep -q "Up"; then
    echo "   ✅ API container: $API"
else
    echo "   ❌ API container not running"
    exit 1
fi

# 7. Network Connectivity
echo "7. Network Connectivity Check..."
NET_OK=$(docker exec nanobot-gateway python -c "
import asyncio
import httpx

async def test():
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get('http://host.docker.internal:8001/health')
            if response.status_code == 200:
                print('OK')
            else:
                print('FAIL')
        except:
            print('FAIL')

asyncio.run(test())
" 2>/dev/null)
if [ "$NET_OK" = "OK" ]; then
    echo "   ✅ Network connectivity OK"
else
    echo "   ❌ Network connectivity failed"
    exit 1
fi

echo ""
echo "=== Stage 2 Quant Tools Integration Tests Complete ==="
echo "All critical tests passed!"
echo ""
echo "Quant tools available:"
echo "  - get_stock_price: 获取股票实时价格"
echo "  - get_stock_info: 获取股票基本信息"
echo "  - get_kline_data: 获取K线数据"
echo "  - search_stocks: 搜索股票"
echo "  - get_market_overview: 获取市场概览"
echo "  - get_market_sentiment: 获取市场情绪"
echo "  - run_backtest: 运行回测"
echo "  - get_backtest_result: 获取回测结果"
echo "  - get_positions: 获取持仓"
echo "  - get_trading_signals: 获取交易信号"
echo "  - get_watchlist: 获取自选股"
echo "  - add_to_watchlist: 添加自选股"
echo "  - execute_trade: 执行交易(Mock)"
echo "  - get_ene_stocks: ENE轨道选股"
echo "  - analyze_strategy_natural_language: 自然语言生成策略"
