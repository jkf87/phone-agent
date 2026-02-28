---
name: phone-agent
description: "AI 실시간 음성 전화 에이전트. Twilio + OpenAI Realtime API로 양방향 음성 대화. 서버 시작, 전화 발신, AI 페르소나/보이스 변경 지원. 사용 시점: (1) 'AI 전화 걸어줘', '모닝콜 해줘' 등 전화 관련 요청, (2) '전화 서버 시작', 'phone agent 시작', (3) 특정 번호로 전화 발신 요청, (4) AI 전화 페르소나 설정/변경"
---

# Phone Agent

OpenAI Realtime API + Twilio로 AI가 실시간 음성 전화를 걸고 대화하는 스킬.

## 사전 요구사항

- Python 3.13+
- ngrok (`brew install ngrok` + authtoken 설정)
- Twilio 계정 (전화번호 + Customer Profile Approved + Geo Permissions: South Korea)
- OpenAI API Key (Realtime API 지원)

## 환경변수 (.env)

스킬 디렉토리에 `.env` 파일 생성:

```
OPENAI_API_KEY="sk-..."
TWILIO_ACCOUNT_SID="ACxxxxxxxx"
TWILIO_AUTH_TOKEN="xxxxxxxx"
TWILIO_PHONE_NUMBER_SID="PNxxxxxxxx"
PORT=8082
```

## 워크플로우

### 1. 서버 시작

```bash
bash scripts/start.sh
```

자동 처리: 기존 프로세스 종료 → ngrok 시작 → URL 감지 → Twilio Webhook 업데이트 → 서버 시작

### 2. 전화 발신

서버 실행 중 상태에서, ngrok URL을 감지 후 Twilio API로 발신:

```bash
# ngrok URL 감지
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import json, sys
d = json.load(sys.stdin)
ts = [t['public_url'] for t in d.get('tunnels',[]) if t.get('proto')=='https']
print(ts[0] if ts else '')
")

# .env 로드
source .env

# 전화 발신 (번호를 +82 형식으로 변환)
curl -X POST "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Calls.json" \
  --data-urlencode "To=+821012345678" \
  --data-urlencode "From=+1XXXXXXXXXX" \
  --data-urlencode "Url=${NGROK_URL}/incoming" \
  --data-urlencode "Timeout=30" \
  -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}"
```

성공 시 `"status": "queued"` 응답, 수 초 후 전화 울림.

한국 번호 변환: `010-1234-5678` → `+821012345678` (0 제거, +82 추가)

### 3. 페르소나 변경

`scripts/server_realtime.py`의 `SYSTEM_PROMPT` 수정:

```python
SYSTEM_PROMPT = """당신은 AI 비서 '하나'예요. 반말로 친근하게 대화해주세요."""
```

### 4. 보이스 변경

`scripts/server_realtime.py`의 `session.update`에서 `voice` 값 변경:

| Voice | 특징 |
|-------|------|
| `shimmer` | 따뜻한 여성 (기본값) |
| `alloy` | 중성적, 균형 |
| `echo` | 차분한 남성 |
| `coral` | 밝고 활기찬 |
| `sage` | 부드럽고 차분 |
| `ash`, `ballad`, `verse`, `marin`, `cedar` | 기타 |

## 핵심 기술 포인트

오디오 포맷 변환 (틀리면 칙칙 소리):
- Twilio→OpenAI: mu-law 8kHz → PCM16 16kHz
- OpenAI→Twilio: PCM16 **24kHz** → mu-law 8kHz (24kHz 필수)

## 문제 해결

| 증상 | 해결 |
|------|------|
| `ModuleNotFoundError: audioop` | `pip3 install --break-system-packages audioop-lts` |
| 칙칙 소리 | `openai_to_twilio_audio`에서 24000→8000 확인 |
| 스페인어/영어로 대답 | voice 이름 유효한지 확인 (fable 등 구형 제거됨) |
| error 10005 | Twilio Customer Profile 생성 + 지원팀 Voice 활성화 요청 |
| 국제전화 수신거부 | 수신자가 통신사에서 국제전화 수신 허용 |

## 설치 (패키지 없을 때)

```bash
pip3 install --break-system-packages fastapi uvicorn twilio websockets audioop-lts
```

## 비용

월 약 $4.3 (~6,000원): Twilio 번호 $1 + 통화 ~$1.3 + OpenAI ~$2
