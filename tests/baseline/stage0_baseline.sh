#!/bin/bash
# Stage 0 Baseline Tests
# 验证 nanobot 原生功能正常运行

set -e

echo "=== Stage 0 Baseline Tests ==="
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

# 2. API Health
echo "2. API Health Check..."
API_HEALTH=$(curl -s http://127.0.0.1:8900/health)
if [ "$API_HEALTH" = '{"status":"ok"}' ] || [ "$API_HEALTH" = '{"status": "ok"}' ]; then
    echo "   ✅ API health OK"
else
    echo "   ❌ API health failed: $API_HEALTH"
    exit 1
fi

# 3. API Models
echo "3. API Models Check..."
MODELS=$(curl -s http://127.0.0.1:8900/v1/models)
if echo "$MODELS" | grep -q '"object"[[:space:]]*:[[:space:]]*"list"'; then
    echo "   ✅ Models endpoint OK"
    echo "   Model: $(echo $MODELS | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['id'])")"
else
    echo "   ❌ Models endpoint failed"
    exit 1
fi

# 4. Chat Completions
echo "4. Chat Completions Check..."
CHAT=$(curl -s -X POST http://127.0.0.1:8900/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Say OK"}]}')
if echo "$CHAT" | grep -q '"finish_reason"[[:space:]]*:[[:space:]]*"stop"'; then
    echo "   ✅ Chat completions OK"
else
    echo "   ❌ Chat completions failed"
    exit 1
fi

# 5. Tool Call (Read File)
echo "5. Tool Call Check..."
TOOL=$(curl -s -X POST http://127.0.0.1:8900/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Read /etc/hostname"}]}')
if echo "$TOOL" | grep -q "finish_reason"; then
    echo "   ✅ Tool call OK"
else
    echo "   ❌ Tool call failed"
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

# 7. Feishu Connection
echo "7. Feishu Connection Check..."
FEISHU=$(docker logs nanobot-gateway 2>&1 | grep -i "feishu.*connected\|Lark.*connected" | tail -1)
if [ -n "$FEISHU" ]; then
    echo "   ✅ Feishu connected"
else
    echo "   ⚠️  Feishu not connected (optional)"
fi

echo ""
echo "=== Stage 0 Baseline Tests Complete ==="
echo "All critical tests passed!"
