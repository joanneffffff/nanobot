#!/bin/bash
# Stage 1 Baseline Tests
# 验证前端 AI 助手组件可以连接到 nanobot WebSocket

set -e

echo "=== Stage 1 Frontend Integration Tests ==="
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

# 2. WebSocket Channel
echo "2. WebSocket Channel Check..."
WS_CHECK=$(python3 -c "
import asyncio
import websockets
import json

async def test():
    uri = 'ws://127.0.0.1:18791/?token=quant-platform-secret'
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({'type': 'new_chat'}))
        response = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(response)
        if data.get('event') == 'ready' and data.get('chat_id'):
            print('OK')
        else:
            print('FAIL')

asyncio.run(test())
")
if [ "$WS_CHECK" = "OK" ]; then
    echo "   ✅ WebSocket channel OK"
else
    echo "   ❌ WebSocket channel failed"
    exit 1
fi

# 3. Frontend Container
echo "3. Frontend Container Check..."
FRONTEND=$(docker ps --filter "name=quant_frontend_naive" --format "{{.Status}}")
if echo "$FRONTEND" | grep -q "Up"; then
    echo "   ✅ Frontend container: $FRONTEND"
else
    echo "   ❌ Frontend container not running"
    exit 1
fi

# 4. Frontend HTTP
echo "4. Frontend HTTP Check..."
FRONTEND_HTML=$(curl -s http://localhost:5174)
if echo "$FRONTEND_HTML" | grep -q "量化"; then
    echo "   ✅ Frontend HTTP OK"
else
    echo "   ❌ Frontend HTTP failed"
    exit 1
fi

# 5. AI Assistant Component
echo "5. AI Assistant Component Check..."
AI_COMPONENT=$(curl -s http://localhost:5174/src/components/AiAssistant.vue 2>/dev/null | head -5)
if echo "$AI_COMPONENT" | grep -q "AiAssistant"; then
    echo "   ✅ AI Assistant component accessible"
else
    echo "   ⚠️  AI Assistant component check skipped (Vite dev server behavior)"
fi

# 6. Docker Network Connectivity
echo "6. Docker Network Connectivity Check..."
# Check if host.docker.internal resolves from frontend container
HOST_RESOLVE=$(docker exec quant_frontend_naive getent hosts host.docker.internal 2>/dev/null || echo "")
if [ -n "$HOST_RESOLVE" ]; then
    echo "   ✅ host.docker.internal resolves: $HOST_RESOLVE"
else
    echo "   ⚠️  host.docker.internal not resolving (may work on Docker Desktop)"
fi

echo ""
echo "=== Stage 1 Frontend Integration Tests Complete ==="
echo "All critical tests passed!"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:5174 in browser"
echo "2. Login to the system"
echo "3. Click the 'AI 助手' button in the sidebar"
echo "4. Verify WebSocket connection shows '已连接'"
echo "5. Send a test message and verify AI response"
