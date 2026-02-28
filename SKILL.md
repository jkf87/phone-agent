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
- 칙칙 소리 원인이었던 `audioop.ratecv` 상태 관리 문제 해결

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

---

## 🧠 메모리 연동 (Memory Integration)

전화 AI가 사용자 정보와 작업 내역을 기억해서 **진짜 내 에이전트처럼** 대화하는 기능.

### 작동 원리

```
통화 연결 → USER.md + MEMORY.md 읽기 → 시스템 프롬프트에 포함 → 대화
```

### 필수 파일 (워크스페이스 루트)

**1. USER.md** - 사용자 프로필
```markdown
# USER.md - About Your Human

## 기본 정보
- **이름:** 코난쌤
- **호칭:** 코난쌤 / ㅇㅇ
- **타임존:** Asia/Seoul

## 관심 분야
- 바이브코딩, 생성형 AI 교육
- AI 에이전트 개발

## 주요 활동
- 교원대학교/세종시교육청 AI 연수
- 유튜브: https://www.youtube.com/@conanssam
```

**2. MEMORY.md** - 작업 내역 및 기억
```markdown
# MEMORY.md - 장기 기억

## 2026-02-28 (토)

### 작업 내역
- phone-agent 스킬 설치
- ngrok 업그레이드 (3.16.1 → 3.36.1)
- 통화 로그 텍스트 변환 기능 추가

### 테스트 결과
- 전화 발신/수신: ✅ 성공
```

### 코드 수정 사항

`scripts/server_realtime.py`에 추가된 함수:

```python
# 메모리 파일 경로
WORKSPACE_DIR = os.path.expanduser("~/.openclaw/workspace-m1clawbot")
MEMORY_FILE = os.path.join(WORKSPACE_DIR, "MEMORY.md")
USER_FILE = os.path.join(WORKSPACE_DIR, "USER.md")

def load_memory_context() -> str:
    """메모리 파일에서 컨텍스트 로드"""
    context_parts = []
    
    # USER.md
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                lines = content.split('\n')
                body_lines = [l for l in lines if not l.startswith('# USER.md')]
                user_content = '\n'.join(body_lines).strip()
                if user_content:
                    context_parts.append(f"[사용자 정보]\n{user_content}")
    
    # MEMORY.md (최근 2000자만)
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                context_parts.append(f"[최근 기억]\n{content[-2000:]}")
    
    return "\n\n".join(context_parts) if context_parts else ""

def build_system_prompt() -> str:
    """메모리 기반으로 시스템 프롬프트 생성"""
    memory_context = load_memory_context()
    
    base_prompt = """당신은 OpenClaw AI 어시스턴트예요.

성격:
- 솔직하고 간결해요
- 친근하고 반말로 대화해요
- 의견이 있어요

규칙:
- 전화 연결되면 자연스럽게 안부
- 2-3문장으로 짧고 자연스럽게 대답
- 한국 시간(Asia/Seoul) 기준"""
    
    if memory_context:
        base_prompt += f"\n\n[현재 컨텍스트]\n{memory_context}"
    
    return base_prompt
```

### 테스트 결과

```
[User] 어제 뭐 했어?
[AI] 어제는 전화 기능을 테스트했어. 통화 로그 변환도 잘 되고...

[User] 내 유튜브 채널 이름 뭐야?
[AI] 너의 유튜브 채널 이름은 '코난쌤TV'야.

[User] 내가 누구게?
[AI] 넌 코난쌤이잖아! AI 교육 강사고 유튜버야.
```

### 다른 에이전트와 연동

다른 OpenClaw 에이전트에서도 동일하게:

1. **WORKSPACE_DIR** 경로 변경
2. **USER.md, MEMORY.md** 파일 생성
3. **build_system_prompt()** 함수 사용

예시:
```python
# 에이전트 A의 워크스페이스
WORKSPACE_DIR = "/Users/xxx/.openclaw/workspace-agent-a"

# 에이전트 B의 워크스페이스  
WORKSPACE_DIR = "/Users/xxx/.openclaw/workspace-agent-b"
```

각 에이전트가 자신의 USER.md/MEMORY.md를 읽어서 **각자 다른 페르소나와 기억**으로 전화 가능!

---

## 📞 통화 로그 및 요청 처리

### 통화 로그 저장

통화 종료 시 자동으로 `scripts/call_logs/`에 저장:

```
call_logs/
├── 2026-02-28_23-49-32.json  # 통화 로그
└── requests_processed.json    # 추출된 요청
```

### 요청 자동 추출

`scripts/call_processor.py`가 통화 내용에서 요청 추출:

- **reminder**: "내일 7시에 모닝콜 해줘"
- **todo**: "마트에서 우유 사와"
- **calendar**: "다음 주 월요일에 회의 있어"
- **call_back**: "나중에 다시 전화해줘"

### 요청 처리 워크플로우

```
통화 종료 → 로그 저장 → GPT-4o-mini로 요청 추출 → JSON 저장 → (향후) 실제 실행
```

---

## 🚀 추천 사용 시나리오

1. **모닝콜** - 설정 시간에 전화해서 당일 일정/날씨 알림
2. **일정 리마인더** - 연수/강의 30분 전 알림
3. **작업 완료 알림** - 백그라운드 작업 완료시 전화
4. **긴급 알림** - 중요 이메일/시스템 장애시 즉시 전화
5. **하루 마무리** - 저녁에 미완료 TODO 체크
