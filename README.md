# Phone Agent

AI 실시간 음성 전화 에이전트. OpenAI Realtime API + Twilio로 전화를 걸어 양방향 음성 대화를 합니다.

```
전화 발신 (Twilio)
  ↓ POST /incoming
FastAPI 서버 (port 8082)
  ↓ WebSocket /media-stream
OpenAI Realtime API (gpt-4o-mini-realtime-preview)
  ↕ 양방향 실시간 음성 대화
```

## 데모 통화 로그

```
09:31:04 - AI: 좋은 아침! 나는 AI 모닝콜 비서 하나야. 잘 잤어?
09:31:23 - AI: 오늘 하루도 멋지게 보내길 바라!
09:31:49 - AI: 언제든지! 오늘 하루도 즐겁게 보내고, 힘내!
```

---

## 셋업

### 1. 계정 준비

| 서비스 | 용도 | 가입 |
|--------|------|------|
| [Twilio](https://twilio.com) | 전화 발신/수신 | 미국 번호 구매 ($1/월) |
| [OpenAI](https://platform.openai.com) | 실시간 음성 대화 | API Key 발급 |
| [ngrok](https://ngrok.com) | 로컬 서버 터널링 | 무료 계정 |

### 2. Twilio 설정

1. **전화번호 구매**: Phone Numbers → Buy a Number → 미국 번호
2. **Customer Profile 생성**: Account → Customer Profiles → 생성 후 Approved 상태 확인
3. **Geo Permissions**: Voice → Settings → Geo Permissions → South Korea 체크
4. **Phone Number SID 확인**: 번호 클릭 → URL의 `PN`으로 시작하는 값

> Customer Profile이 Approved 되어도 Voice가 안 되면 Twilio 지원팀에 Voice 활성화 요청이 필요할 수 있습니다.

### 3. ngrok 설치

```bash
brew install ngrok
ngrok config add-authtoken 여기에_토큰
```

### 4. Python 패키지 설치

```bash
pip3 install fastapi uvicorn twilio websockets audioop-lts
```

> Python 3.13+에서는 `audioop-lts` 필수

### 5. .env 파일 생성

프로젝트 루트에 `.env` 파일 생성:

```bash
OPENAI_API_KEY="sk-..."
TWILIO_ACCOUNT_SID="ACxxxxxxxx"
TWILIO_AUTH_TOKEN="xxxxxxxx"
TWILIO_PHONE_NUMBER_SID="PNxxxxxxxx"
PORT=8082
```

---

## 사용법

### 서버 시작 (원클릭)

```bash
bash scripts/start.sh
```

자동으로 처리됨:
1. 기존 서버 종료
2. ngrok 시작 + HTTPS URL 감지
3. Twilio Webhook 자동 업데이트
4. 서버 시작

### 전화 걸기

```bash
source .env

NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import json, sys
d = json.load(sys.stdin)
ts = [t['public_url'] for t in d.get('tunnels',[]) if t.get('proto')=='https']
print(ts[0] if ts else '')
")

curl -X POST "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Calls.json" \
  --data-urlencode "To=+821012345678" \
  --data-urlencode "From=+1XXXXXXXXXX" \
  --data-urlencode "Url=${NGROK_URL}/incoming" \
  --data-urlencode "Timeout=30" \
  -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}"
```

한국 번호 변환: `010-1234-5678` → `+821012345678`

---

## 커스터마이징

### AI 페르소나 변경

`scripts/server_realtime.py`의 `SYSTEM_PROMPT` 수정:

```python
# 한국어 모닝콜
SYSTEM_PROMPT = """당신은 AI 모닝콜 비서 '하나'예요. 반말로 친근하게..."""

# 영어 회화 파트너
SYSTEM_PROMPT = """You are Sarah, a friendly English conversation partner..."""
```

### 보이스 변경

`VOICE` 변수 변경:

| Voice | 특징 |
|-------|------|
| `shimmer` | 따뜻한 여성 (기본값) |
| `alloy` | 중성적, 균형 |
| `echo` | 차분한 남성 |
| `coral` | 밝고 활기찬 |
| `sage` | 부드럽고 차분 |

---

## 문제 해결

| 증상 | 해결 |
|------|------|
| `ModuleNotFoundError: audioop` | `pip3 install audioop-lts` |
| 칙칙 소리 | 오디오 변환 24000→8000 확인 |
| 스페인어/영어로 대답 | voice 이름 유효한지 확인 (`fable` 등 구형 제거됨) |
| error 10005 | Twilio Customer Profile + Voice 활성화 |
| 국제전화 수신거부 | 수신자가 통신사에서 국제전화 수신 허용 |

---

## 비용

월 약 $4.3 (~6,000원)

| 서비스 | 월 비용 |
|--------|---------|
| Twilio 번호 | $1 |
| Twilio 통화 (하루 10분 × 22일) | ~$1.3 |
| OpenAI Realtime | ~$2 |
| ngrok | 무료 |

---

## Claude Code 스킬로 사용

```bash
# 스킬 설치
claude install-skill phone-agent.skill

# 이후 자연어로 사용
# "전화 서버 시작해줘"
# "01012345678로 전화 걸어줘"
# "모닝콜 페르소나 영어 회화 파트너로 바꿔줘"
```

## 라이선스

MIT
