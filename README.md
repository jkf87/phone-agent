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

## 빠른 시작 (Quick Start)

### 1. 계정 준비

| 서비스 | 용도 | 가입 |
|--------|------|------|
| [Twilio](https://twilio.com) | 전화 발신/수신 | 미국 번호 구매 ($1/월) |
| [OpenAI](https://platform.openai.com) | 실시간 음성 대화 | API Key 발급 |
| [ngrok](https://ngrok.com) | 로컬 서버 터널링 | 무료 계정 + authtoken 필수 |

### 2. Twilio 설정

1. **전화번호 구매**: Phone Numbers → Buy a Number → 미국 번호
2. **Customer Profile 생성**: Account → Customer Profiles → 생성 후 Approved 상태 확인
3. **Geo Permissions**: Voice → Settings → Geo Permissions → South Korea 체크
4. **Phone Number SID 확인**: 번호 클릭 → URL의 `PN`으로 시작하는 값

> Customer Profile이 Approved 되어도 Voice가 안 되면 Twilio 지원팀에 Voice 활성화 요청이 필요할 수 있습니다.

### 3. 초기 설정 (최초 1회)

```bash
bash scripts/setup.sh
```

자동 처리: Python 패키지 설치 → ngrok 확인 → .env 템플릿 생성

setup.sh 실행 후 `.env` 파일에 API 키를 채워넣으세요:

```bash
OPENAI_API_KEY="sk-..."
TWILIO_ACCOUNT_SID="ACxxxxxxxx"
TWILIO_AUTH_TOKEN="xxxxxxxx"
TWILIO_PHONE_NUMBER_SID="PNxxxxxxxx"
NGROK_AUTHTOKEN="2xxx..."
PORT=8082
```

> `NGROK_AUTHTOKEN`을 .env에 넣으면 ngrok config 없이 자동 인증됩니다.

---

## 사용법

### 서버 시작 (원클릭)

```bash
bash scripts/start.sh
```

자동으로 처리됨:
1. 의존성 체크 (없으면 자동 설치)
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

변경 후 start.sh를 다시 실행해야 반영됩니다.

### 보이스 변경

`VOICE` 변수 변경:

| Voice | 특징 |
|-------|------|
| `shimmer` | 밝고 에너지 넘치는 (기본값) |
| `alloy` | 중성적, 균형 |
| `echo` | 차분한 남성 |
| `coral` | 따뜻하고 친근한 |
| `sage` | 부드럽고 차분한 |
| `ash` | 또렷하고 명확한 |
| `ballad` | 감성적이고 부드러운 |
| `verse` | 다재다능한 |

---

## 문제 해결

| 증상 | 해결 |
|------|------|
| 칙칙 소리 | g711_ulaw 포맷 사용 확인 (pcm16은 변환 시 칙칙거림) |
| 스페인어/영어로 대답 | voice 이름 유효한지 확인 (`fable` 등 구형 제거됨) |
| error 10005 | Twilio Customer Profile + Voice 활성화 |
| 국제전화 수신거부 | 수신자가 통신사에서 국제전화 수신 허용 |
| ngrok 세션 제한 | 무료 계정 동시 1세션. 다른 기기 ngrok 종료 또는 [dashboard.ngrok.com/agents](https://dashboard.ngrok.com/agents)에서 세션 종료 |
| .env 값 비어있음 | `bash scripts/setup.sh` 실행 후 값 채우기 |

---

## 비용

월 약 $17 (~24,000원) — 하루 3분, 평일 22일 기준

| 서비스 | 월 비용 |
|--------|---------|
| Twilio 번호 | $1 |
| Twilio 통화 (66분 × $0.05) | ~$4.3 |
| OpenAI Realtime (66분 × $0.20) | ~$13 |
| ngrok | 무료 |

> gpt-4o-mini-realtime-preview 기준. 통화 시간을 줄이면 비용도 줄어듭니다.

---

## 라이선스

MIT
