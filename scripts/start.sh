#!/bin/bash
# Phone Agent 원클릭 시작: 의존성 체크 → ngrok → Twilio Webhook → 서버
# Mac과 Linux/WSL 모두 지원

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Python 명령어 감지
PYTHON_CMD="python3"
if ! command -v python3 &>/dev/null; then
  if command -v python &>/dev/null; then
    PYTHON_CMD="python"
  else
    echo "✗ Python이 설치되지 않았어요."
    exit 1
  fi
fi

# venv 자동 감지 (setup.sh에서 venv 생성한 경우)
if [ -f "$SKILL_DIR/venv/bin/activate" ]; then
  source "$SKILL_DIR/venv/bin/activate"
  PYTHON_CMD="python3"
  echo "✓ venv 활성화됨"
fi

# 의존성 체크 (최초 실행 시 자동 설치)
if ! "$PYTHON_CMD" -c "import fastapi, uvicorn, twilio, websockets, audioop" 2>/dev/null; then
  echo "→ Python 패키지 설치 중..."
  "$PYTHON_CMD" -m pip install --break-system-packages -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null \
    || "$PYTHON_CMD" -m pip install -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null \
    || { echo "✗ 패키지 설치 실패. 'bash scripts/setup.sh'를 먼저 실행하세요."; exit 1; }
  echo "✓ 패키지 설치 완료"
fi

# ngrok 설치 확인
if ! command -v ngrok &>/dev/null; then
  echo "✗ ngrok이 설치되지 않았어요."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  설치: brew install ngrok"
  else
    echo "  설치: sudo snap install ngrok"
    echo "  또는: sudo apt install ngrok"
  fi
  echo "  인증: ngrok config add-authtoken 여기에_토큰"
  echo "  또는: bash $SCRIPT_DIR/setup.sh"
  exit 1
fi

# .env 로드
if [ -f "$SKILL_DIR/.env" ]; then
  set -a; source "$SKILL_DIR/.env"; set +a
  echo "✓ .env 로드됨"
else
  echo "✗ .env 파일 없음. setup.sh로 생성하세요:"
  echo "  bash $SCRIPT_DIR/setup.sh"
  exit 1
fi

# .env의 PORT 값 반영 (기본값 8082)
SERVER_PORT="${PORT:-8082}"

# 필수 환경변수 체크
MISSING=""
[ -z "$OPENAI_API_KEY" ] && MISSING="$MISSING OPENAI_API_KEY"
[ -z "$TWILIO_ACCOUNT_SID" ] && MISSING="$MISSING TWILIO_ACCOUNT_SID"
[ -z "$TWILIO_AUTH_TOKEN" ] && MISSING="$MISSING TWILIO_AUTH_TOKEN"
[ -z "$TWILIO_PHONE_NUMBER_SID" ] && MISSING="$MISSING TWILIO_PHONE_NUMBER_SID"
if [ -n "$MISSING" ]; then
  echo "✗ .env에 빈 값이 있어요:$MISSING"
  echo "  .env 파일을 열어서 값을 채워주세요: $SKILL_DIR/.env"
  exit 1
fi

# 기존 서버 종료
pkill -f "server_realtime.py" 2>/dev/null

# ngrok 시작/재사용
if curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -q "public_url"; then
  echo "✓ ngrok 실행 중"
else
  echo "→ ngrok 시작..."
  pkill -f "ngrok" 2>/dev/null; sleep 1
  ngrok http "$SERVER_PORT" > /dev/null 2>&1 &
  for i in {1..10}; do
    sleep 1
    curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -q "public_url" && break
    [ $i -eq 10 ] && echo "✗ ngrok 시작 실패. authtoken이 설정됐는지 확인하세요." && exit 1
  done
fi

# ngrok URL 추출
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | "$PYTHON_CMD" -c "
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
  RESULT=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 -X POST \
    "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/IncomingPhoneNumbers/${TWILIO_PHONE_NUMBER_SID}.json" \
    --data-urlencode "VoiceUrl=${NGROK_URL}/incoming" \
    -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}")
  if [ "$RESULT" = "200" ]; then
    echo "✓ Twilio Webhook 업데이트 완료"
  else
    echo "✗ Webhook 업데이트 실패 (HTTP $RESULT)"
    echo "  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER_SID를 확인하세요."
    exit 1
  fi
fi

# 서버 시작 (반드시 server_realtime.py 사용)
echo "→ 서버 시작 (port $SERVER_PORT)..."
exec "$PYTHON_CMD" "$SCRIPT_DIR/server_realtime.py"
