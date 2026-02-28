---
name: phone-agent
description: "AI 실시간 음성 전화 에이전트 (OpenAI Realtime API 전용). Twilio + OpenAI Realtime API만 사용. Deepgram, ElevenLabs 불필요. 서버 파일은 반드시 scripts/server_realtime.py를 사용할 것 (server.py 아님). 사용 시점: (1) 'AI 전화 걸어줘', '모닝콜 해줘' 등 전화 관련 요청, (2) '전화 서버 시작', 'phone agent 시작', (3) 특정 번호로 전화 발신 요청, (4) AI 전화 페르소나 설정/변경"
---

# Phone Agent (OpenAI Realtime API 전용)

OpenAI Realtime API + Twilio로 AI가 실시간 음성 전화를 걸고 대화하는 스킬.

**중요: 이 스킬은 Deepgram, ElevenLabs를 사용하지 않음.** OpenAI Realtime API가 음성 인식 + AI 대화 + 음성 합성을 모두 처리. 필요한 API 키는 OpenAI + Twilio 두 개뿐.

## 사전 요구사항

- Python 3.11+
- ngrok (authtoken 설정 필수, 무료 계정 동시 1세션 제한)
- Twilio 계정 (전화번호 + Customer Profile Approved + Geo Permissions: South Korea)
- OpenAI API Key (Realtime API 지원)

## 초기 설정 (최초 1회)

```bash
bash scripts/setup.sh
```

자동 처리: Python 패키지 설치 → ngrok 확인 → .env 템플릿 생성

Mac, Linux/WSL, Windows(WSL) 모두 지원. setup.sh 실행 후 `.env` 파일에 API 키를 채워넣으면 준비 완료.

## 환경변수 (.env)

스킬 디렉토리의 `.env` 파일 (setup.sh가 자동 생성):

```
OPENAI_API_KEY="sk-..."
TWILIO_ACCOUNT_SID="ACxxxxxxxx"
TWILIO_AUTH_TOKEN="xxxxxxxx"
TWILIO_PHONE_NUMBER_SID="PNxxxxxxxx"
NGROK_AUTHTOKEN="2xxx..."  # dashboard.ngrok.com → Your Authtoken
PORT=8082
MY_PHONE="+821012345678"  # (선택) make-call.sh에서 기본 수신번호로 사용
```

**Deepgram, ElevenLabs 키는 필요 없음.** `PUBLIC_URL_REALTIME`은 start.sh가 자동 설정. `NGROK_AUTHTOKEN`을 .env에 넣으면 ngrok config 없이 자동 인증.

## 워크플로우

### 1. 서버 시작

```bash
bash scripts/start.sh
```

자동 처리: 의존성 체크(없으면 자동 설치) → ngrok 시작 → URL 감지 → Twilio Webhook 업데이트 → `scripts/server_realtime.py` 실행

**주의: server.py가 아닌 server_realtime.py를 실행해야 함.** start.sh가 올바른 파일을 자동 실행.

### 2. 전화 발신

서버 실행 중 상태에서:

```bash
bash scripts/make-call.sh +821012345678
```

또는 수동으로:

```bash
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import json, sys
d = json.load(sys.stdin)
ts = [t['public_url'] for t in d.get('tunnels',[]) if t.get('proto')=='https']
print(ts[0] if ts else '')
")

source .env

curl -X POST "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Calls.json" \
  --data-urlencode "To=+821012345678" \
  --data-urlencode "From=$(curl -s "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/IncomingPhoneNumbers/${TWILIO_PHONE_NUMBER_SID}.json" -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}" | python3 -c "import json,sys;print(json.load(sys.stdin).get('phone_number',''))")" \
  --data-urlencode "Url=${NGROK_URL}/incoming" \
  --data-urlencode "Timeout=30" \
  -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}"
```

한국 번호 변환: `010-1234-5678` → `+821012345678` (0 제거, +82 추가)

### 3. 페르소나 변경

`scripts/server_realtime.py`의 `SYSTEM_PROMPT` 수정 후 start.sh 재실행:

```python
SYSTEM_PROMPT = """당신은 AI 비서 '하나'예요. 반말로 친근하게 대화해주세요."""
```

### 4. 보이스 변경

`scripts/server_realtime.py`의 `VOICE` 변수 변경:

| Voice | 특징 |
|-------|------|
| `shimmer` | 밝고 에너지 넘치는 (기본값) |
| `alloy` | 중성적, 균형 |
| `echo` | 차분한 남성 |
| `coral` | 따뜻하고 친근한 |
| `sage` | 부드럽고 차분한 |
| `ash`, `ballad`, `verse`, `marin`, `cedar` | 기타 |

## 핵심 기술 포인트

오디오 포맷: **g711_ulaw** (Twilio와 OpenAI가 동일 포맷 사용)
- Twilio mu-law 8kHz ↔ OpenAI g711_ulaw: 변환 없이 직접 패스스루
- audioop 불필요 (Python 3.13+ 호환 문제 없음)

음성 인식: `input_audio_transcription: { model: "whisper-1" }` 설정으로 대화 내용이 서버 로그에 텍스트로 표시됨

## 문제 해결

| 증상 | 해결 |
|------|------|
| 칙칙 소리 | g711_ulaw 포맷 사용 확인 (pcm16은 변환 필요해 칙칙거림) |
| 스페인어/영어로 대답 | voice 이름 유효한지 확인 (fable 등 구형 제거됨), SYSTEM_PROMPT가 한국어인지 확인 |
| error 10005 | Twilio Customer Profile 생성 + 지원팀 Voice 활성화 요청 |
| 국제전화 수신거부 | 수신자가 통신사에서 국제전화 수신 허용 |
| .env 값 비어있음 | `bash scripts/setup.sh` 실행 후 .env에 API 키 채우기 |
| ngrok 없음 | Mac: `brew install ngrok` / Linux: `snap install ngrok` 또는 직접 다운로드 |
| ngrok 세션 제한 | 무료 계정 동시 1세션. 다른 기기 ngrok 종료 또는 dashboard.ngrok.com/agents에서 세션 종료 |
| application error + 5초 끊김 | server_realtime.py 실행 확인 (server.py 아님) |

## 비용

월 약 $17.5 (~24,000원): Twilio 번호 $1 + 통화 ~$3.3 (66분×$0.05) + OpenAI Realtime ~$13.2 (66분×$0.20)
기준: 하루 3분, 평일 22일 사용 (gpt-4o-mini-realtime-preview)
