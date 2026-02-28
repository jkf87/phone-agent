#!/bin/bash
# Phone Agent 전화 발신 스크립트
# 사용법: bash scripts/make-call.sh +821012345678
#         bash scripts/make-call.sh 01012345678

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

# venv 자동 감지
if [ -f "$SKILL_DIR/venv/bin/activate" ]; then
  source "$SKILL_DIR/venv/bin/activate"
  PYTHON_CMD="python3"
fi

# .env 로드
if [ -f "$SKILL_DIR/.env" ]; then
  set -a; source "$SKILL_DIR/.env"; set +a
else
  echo "✗ .env 파일 없음. setup.sh를 먼저 실행하세요."
  exit 1
fi

# 전화번호 인자
TO_NUMBER="$1"
if [ -z "$TO_NUMBER" ]; then
  # .env에 MY_PHONE이 있으면 사용
  if [ -n "$MY_PHONE" ]; then
    TO_NUMBER="$MY_PHONE"
  else
    echo "사용법: bash scripts/make-call.sh +821012345678"
    echo "   또는: bash scripts/make-call.sh 01012345678"
    echo "   또는: .env에 MY_PHONE=\"+821012345678\" 추가"
    exit 1
  fi
fi

# 한국 번호 변환: 010-1234-5678 → +821012345678
TO_NUMBER=$(echo "$TO_NUMBER" | tr -d ' -.()' )
if [[ "$TO_NUMBER" == 0* ]]; then
  TO_NUMBER="+82${TO_NUMBER:1}"
fi

# 번호 형식 검증
if [[ ! "$TO_NUMBER" =~ ^\+[0-9]{10,15}$ ]]; then
  echo "✗ 전화번호 형식이 올바르지 않아요: $TO_NUMBER"
  echo "  예시: +821012345678 또는 01012345678"
  exit 1
fi

# ngrok URL 감지
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | "$PYTHON_CMD" -c "
import json, sys
try:
    d = json.load(sys.stdin)
    ts = [t['public_url'] for t in d.get('tunnels',[]) if t.get('proto')=='https']
    print(ts[0] if ts else '')
except Exception as e:
    print('', file=sys.stderr)
" 2>/dev/null)

if [ -z "$NGROK_URL" ]; then
  echo "✗ ngrok이 실행 중이 아니에요. start.sh를 먼저 실행하세요."
  exit 1
fi

# Twilio에서 From 번호 가져오기
FROM_RESULT=$(curl -s --connect-timeout 10 --max-time 30 \
  "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/IncomingPhoneNumbers/${TWILIO_PHONE_NUMBER_SID}.json" \
  -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}" 2>/dev/null)

FROM_NUMBER=$("$PYTHON_CMD" -c "
import json, sys
try:
    d = json.loads('''$FROM_RESULT''')
    num = d.get('phone_number','')
    if num:
        print(num)
    else:
        err = d.get('message', 'Unknown error')
        print(f'ERROR:{err}', file=sys.stderr)
except Exception as e:
    print(f'ERROR:{e}', file=sys.stderr)
" 2>/dev/null)

if [ -z "$FROM_NUMBER" ]; then
  echo "✗ Twilio에서 전화번호를 가져올 수 없어요."
  echo "  .env의 TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER_SID를 확인하세요."
  exit 1
fi

echo "📞 전화 발신 중..."
echo "   From: $FROM_NUMBER (Twilio)"
echo "   To:   $TO_NUMBER"
echo "   URL:  ${NGROK_URL}/incoming"

# 전화 발신
RESULT=$(curl -s --connect-timeout 10 --max-time 30 -X POST \
  "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Calls.json" \
  --data-urlencode "To=${TO_NUMBER}" \
  --data-urlencode "From=${FROM_NUMBER}" \
  --data-urlencode "Url=${NGROK_URL}/incoming" \
  --data-urlencode "Timeout=30" \
  -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}")

# 결과 파싱
STATUS=$("$PYTHON_CMD" -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    if 'status' in d:
        print(f\"✓ 발신 성공! (status: {d['status']})\")
        print(f\"  Call SID: {d.get('sid','')}\")
    elif 'message' in d:
        print(f\"✗ 실패: {d['message']}\")
        if 'code' in d:
            print(f\"  Error code: {d['code']}\")
    else:
        print(f'✗ 예상치 못한 응답: {json.dumps(d, indent=2)}')
except Exception as e:
    print(f'✗ 응답 파싱 실패: {e}')
" <<< "$RESULT" 2>/dev/null)

if [ -z "$STATUS" ]; then
  echo "✗ Twilio 응답을 파싱할 수 없어요."
  echo "  원본 응답: $RESULT"
else
  echo "$STATUS"
fi
