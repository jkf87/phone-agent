#!/bin/bash
# Phone Agent 초기 설정: 의존성 설치 + .env 템플릿 생성 + ngrok 체크
# Mac과 Linux/WSL 모두 지원. 최초 1회만 실행하면 됨.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Phone Agent 초기 설정 ==="
echo ""

# OS 감지
OS="unknown"
if [[ "$OSTYPE" == "darwin"* ]]; then
  OS="mac"
elif [[ "$OSTYPE" == "linux"* ]]; then
  OS="linux"
fi
echo "→ 운영체제: $OS"

# 1. Python 확인
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
  PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
  PYTHON_CMD="python"
else
  echo "✗ Python이 설치되지 않았어요."
  if [ "$OS" = "mac" ]; then
    echo "  설치: brew install python3"
  else
    echo "  설치: sudo apt install python3 python3-pip"
  fi
  exit 1
fi

PYTHON_VER=$($PYTHON_CMD --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
echo "✓ Python $PYTHON_VER 감지됨 ($PYTHON_CMD)"

# 2. Python 패키지 설치
echo ""
echo "→ Python 패키지 설치 중..."

# 가상환경 사용 여부 확인 (externally-managed 환경 대응)
INSTALL_CMD="$PYTHON_CMD -m pip install"

# --break-system-packages 시도 → 실패하면 일반 pip → 실패하면 venv 생성
if $INSTALL_CMD --break-system-packages -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null; then
  echo "✓ 패키지 설치 완료 (system)"
elif $INSTALL_CMD -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null; then
  echo "✓ 패키지 설치 완료"
else
  echo "→ 시스템 Python에 설치 불가. 가상환경 생성 중..."
  VENV_DIR="$SKILL_DIR/venv"
  "$PYTHON_CMD" -m venv "$VENV_DIR" 2>/dev/null || { echo "✗ venv 생성 실패"; exit 1; }
  source "$VENV_DIR/bin/activate"
  PYTHON_CMD="python3"
  INSTALL_CMD="$PYTHON_CMD -m pip install"
  pip install -r "$SCRIPT_DIR/requirements.txt" || { echo "✗ venv 패키지 설치 실패"; exit 1; }
  echo "✓ 패키지 설치 완료 (venv: $VENV_DIR)"
  echo "  start.sh가 venv를 자동 감지하므로 별도 활성화 불필요"
fi

# 3. ngrok 설치 확인
echo ""
if command -v ngrok &>/dev/null; then
  echo "✓ ngrok 설치됨"
else
  echo "✗ ngrok이 설치되지 않았어요."
  if [ "$OS" = "mac" ]; then
    echo "  설치: brew install ngrok"
  else
    echo "  설치 방법 1: sudo snap install ngrok"
    echo "  설치 방법 2:"
    echo "    curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null"
    echo "    echo 'deb https://ngrok-agent.s3.amazonaws.com buster main' | sudo tee /etc/apt/sources.list.d/ngrok.list"
    echo "    sudo apt update && sudo apt install ngrok"
  fi
  echo ""
  echo "  설치 후 인증 (둘 중 하나):"
  echo "    방법1: .env에 NGROK_AUTHTOKEN=\"여기에_토큰\" 추가 (추천)"
  echo "    방법2: ngrok config add-authtoken 여기에_토큰"
  echo "  토큰은 https://dashboard.ngrok.com 에서 가입 후 복사"
fi

# 4. .env 파일 생성 (없을 때만)
echo ""
ENV_FILE="$SKILL_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  echo "✓ .env 파일 존재: $ENV_FILE"

  # 빈 값 체크
  MISSING=""
  for VAR in OPENAI_API_KEY TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_PHONE_NUMBER_SID; do
    VAL=$(grep "^${VAR}=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    if [ -z "$VAL" ]; then
      MISSING="$MISSING $VAR"
    fi
  done

  if [ -n "$MISSING" ]; then
    echo "⚠ 아직 값이 비어있는 변수:$MISSING"
    echo "  .env 파일을 열어서 값을 채워주세요: $ENV_FILE"
  else
    echo "✓ 모든 환경변수가 설정됨"
  fi
else
  cat > "$ENV_FILE" << 'ENVEOF'
# Phone Agent 환경변수 (OpenAI Realtime API 전용)
# Deepgram, ElevenLabs 키는 필요 없음

# OpenAI API Key (platform.openai.com → API keys)
OPENAI_API_KEY=""

# Twilio (console.twilio.com 메인 화면)
TWILIO_ACCOUNT_SID=""
TWILIO_AUTH_TOKEN=""

# Twilio 전화번호 SID (Phone Numbers → 번호 클릭 → URL의 PN값)
TWILIO_PHONE_NUMBER_SID=""

# ngrok authtoken (dashboard.ngrok.com → Your Authtoken)
# .env에 넣으면 ngrok config 없이 자동 인증됨
NGROK_AUTHTOKEN=""

# 서버 포트 (변경하지 않아도 됨)
PORT=8082

# 내 전화번호 (선택, make-call.sh에서 기본 수신번호로 사용)
# MY_PHONE="+821012345678"
ENVEOF
  echo "✓ .env 파일 생성됨: $ENV_FILE"
  echo "  ⚠ 반드시 .env 파일을 열어서 API 키와 Twilio 정보를 입력하세요!"
fi

# 5. 결과 요약
echo ""
echo "=== 설정 완료 ==="
echo ""
echo "이 스킬은 OpenAI Realtime API 전용입니다."
echo "Deepgram, ElevenLabs 키는 필요 없습니다."
echo ""
echo "다음 단계:"
echo "  1. .env 파일에 API 키 + NGROK_AUTHTOKEN 입력: $ENV_FILE"
echo "  2. ngrok 설치 (아직 안 했다면)"
echo "  3. 서버 시작: bash $SCRIPT_DIR/start.sh"
echo "  4. 전화 발신: bash $SCRIPT_DIR/make-call.sh +821012345678"
echo ""
