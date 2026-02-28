#!/bin/bash
# Phone Agent 원클릭 시작: ngrok + Twilio Webhook 업데이트 + 서버

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_PORT=8082

# .env 로드
if [ -f "$SKILL_DIR/.env" ]; then
  set -a; source "$SKILL_DIR/.env"; set +a
  echo "✓ .env 로드됨"
else
  echo "✗ .env 파일 없음: $SKILL_DIR/.env"
  echo "  OPENAI_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER_SID 필요"
  exit 1
fi

# 기존 서버 종료
pkill -f "server_realtime.py" 2>/dev/null

# ngrok 시작/재사용
if curl -s http://localhost:4040/api/tunnels | grep -q "public_url"; then
  echo "✓ ngrok 실행 중"
else
  echo "→ ngrok 시작..."
  pkill -f "ngrok" 2>/dev/null; sleep 1
  ngrok http $SERVER_PORT > /dev/null 2>&1 &
  for i in {1..10}; do
    sleep 1
    curl -s http://localhost:4040/api/tunnels | grep -q "public_url" && break
    [ $i -eq 10 ] && echo "✗ ngrok 시작 실패" && exit 1
  done
fi

# ngrok URL 추출
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import json, sys
d = json.load(sys.stdin)
ts = [t['public_url'] for t in d.get('tunnels',[]) if t.get('proto')=='https']
print(ts[0] if ts else '')
")
[ -z "$NGROK_URL" ] && echo "✗ ngrok URL 감지 실패" && exit 1
echo "✓ ngrok URL: $NGROK_URL"
export PUBLIC_URL_REALTIME="$NGROK_URL"

# Twilio Webhook 업데이트
if [ -n "$TWILIO_ACCOUNT_SID" ] && [ -n "$TWILIO_AUTH_TOKEN" ] && [ -n "$TWILIO_PHONE_NUMBER_SID" ]; then
  RESULT=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/IncomingPhoneNumbers/${TWILIO_PHONE_NUMBER_SID}.json" \
    --data-urlencode "VoiceUrl=${NGROK_URL}/incoming" \
    -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}")
  [ "$RESULT" = "200" ] && echo "✓ Twilio Webhook 업데이트 완료" || echo "✗ Webhook 업데이트 실패 (HTTP $RESULT)"
fi

# 서버 시작
echo "→ 서버 시작 (port $SERVER_PORT)..."
exec python3 "$SCRIPT_DIR/server_realtime.py"
