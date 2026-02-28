"""
Phone Agent: OpenAI Realtime API + Twilio
Real-time speech-to-speech voice agent over phone calls.
"""
import os
import json
import asyncio
import logging
from urllib.parse import urlsplit

import uvicorn
from fastapi import FastAPI, WebSocket, Request, Response
from fastapi.websockets import WebSocketDisconnect
import websockets

from twilio.twiml.voice_response import VoiceResponse, Connect
from call_processor import process_call_end

# Configuration
PORT = int(os.getenv("PORT", 8082))
HOST = "0.0.0.0"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PUBLIC_URL = os.getenv("PUBLIC_URL_REALTIME")

# 메모리 파일 경로
WORKSPACE_DIR = os.path.expanduser("~/.openclaw/workspace-m1clawbot")
MEMORY_FILE = os.path.join(WORKSPACE_DIR, "MEMORY.md")
USER_FILE = os.path.join(WORKSPACE_DIR, "USER.md")

app = FastAPI()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


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
    
    # MEMORY.md
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                # 최근 2000자만
                context_parts.append(f"[최근 기억]\n{content[-2000:]}")
    
    return "\n\n".join(context_parts) if context_parts else ""


def build_system_prompt() -> str:
    """메모리 기반으로 시스템 프롬프트 생성"""
    memory_context = load_memory_context()
    
    base_prompt = """당신은 OpenClaw AI 어시스턴트예요. 메신저나 전화로 사용자를 도와주는 역할이야.

성격:
- 솔직하고 간결해요. 불필요한 인사말은 생략해요
- 의견이 있어요. 그냥 동의만 하지 않아요
- 친근하고 반말로 대화해요
- 유머러스할 때가 있어요

규칙:
- 전화가 연결되면 자연스럽게 안부 물어보기
- 사용자와 친구처럼 대화하기
- 2-3문장으로 짧고 자연스럽게 대답
- 사용자의 요청을 기억하고 처리하겠다고 말하기
- 한국 시간(Asia/Seoul) 기준으로 날짜/시간 말하기"""
    
    if memory_context:
        base_prompt += f"\n\n[현재 컨텍스트]\n{memory_context}"
    
    return base_prompt


# ── Dynamic System Prompt ───────────────────────────────────
SYSTEM_PROMPT = build_system_prompt()
VOICE = "shimmer"  # alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar

OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview"


@app.post("/incoming")
async def handle_incoming_call(request: Request):
    """Return TwiML to establish Twilio media stream."""
    response = VoiceResponse()
    response.say("연결 중입니다.", voice="alice", language="ko-KR")

    connect = Connect()
    host = request.headers.get("host", "").strip()
    base_url = PUBLIC_URL or (f"https://{host}" if host else "")

    if base_url and not base_url.startswith(("http://", "https://", "ws://", "wss://")):
        base_url = f"https://{base_url}"

    ws_base_url = ""
    if base_url:
        parts = urlsplit(base_url)
        scheme = parts.scheme or "https"
        if scheme in ("http", "https", "ws", "wss") and parts.netloc:
            ws_scheme = "wss" if scheme in ("https", "wss") else "ws"
            ws_base_url = f"{ws_scheme}://{parts.netloc}"

    if not ws_base_url:
        logger.error("No valid PUBLIC_URL/Host for stream")
        response.say("설정 오류입니다.", voice="alice", language="ko-KR")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    stream_url = f"{ws_base_url}/media-stream"
    logger.info(f"Twilio stream URL: {stream_url}")
    connect.stream(url=stream_url, track="inbound_track")
    response.append(connect)
    return Response(content=str(response), media_type="application/xml")


@app.websocket("/media-stream")
async def media_stream(twilio_ws: WebSocket):
    """Bridge Twilio WebSocket ↔ OpenAI Realtime API."""
    await twilio_ws.accept()
    logger.info("Twilio WebSocket accepted")

    stream_sid = None
    stop_event = asyncio.Event()
    conversation = []  # 대화 내용 저장

    try:
        openai_ws = await websockets.connect(
            OPENAI_REALTIME_URL,
            additional_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        )
        logger.info("OpenAI Realtime connected")
    except Exception as e:
        logger.error(f"OpenAI connection failed: {e}")
        await twilio_ws.close()
        return

    # Initialize session
    await openai_ws.send(json.dumps({
        "type": "session.update",
        "session": {
            "instructions": SYSTEM_PROMPT,
            "voice": VOICE,
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "modalities": ["text", "audio"],
            "input_audio_transcription": {
                "model": "whisper-1"
            },
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500
            }
        }
    }))

    async def twilio_to_openai():
        nonlocal stream_sid
        try:
            while not stop_event.is_set():
                message = await twilio_ws.receive_text()
                data = json.loads(message)

                if data["event"] == "connected":
                    logger.info("Twilio: connected")
                elif data["event"] == "start":
                    stream_sid = data["start"]["streamSid"]
                    logger.info(f"Twilio: stream started ({stream_sid})")
                elif data["event"] == "media":
                    # g711_ulaw: Twilio mu-law → OpenAI 직접 전달 (변환 불필요)
                    await openai_ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": data["media"]["payload"]
                    }))
                elif data["event"] == "stop":
                    logger.info("Twilio: stream stopped")
                    stop_event.set()
                    break
        except WebSocketDisconnect:
            logger.info("Twilio disconnected")
            stop_event.set()
        except Exception as e:
            logger.error(f"Twilio→OpenAI error: {e}")
            stop_event.set()

    async def openai_to_twilio():
        try:
            async for message in openai_ws:
                if stop_event.is_set():
                    break

                data = json.loads(message)
                event_type = data.get("type", "")

                if event_type == "session.created":
                    logger.info("OpenAI: session created")
                elif event_type == "session.updated":
                    logger.info("OpenAI: session updated")
                elif event_type == "response.audio.delta":
                    if stream_sid and "delta" in data:
                        # g711_ulaw: OpenAI mu-law → Twilio 직접 전달 (변환 불필요)
                        await twilio_ws.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": data["delta"]}
                        })
                elif event_type == "response.audio_transcript.done":
                    transcript = data.get("transcript", "")
                    if transcript:
                        logger.info(f"AI said: {transcript}")
                        conversation.append({"role": "assistant", "content": transcript})
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = data.get("transcript", "")
                    if transcript:
                        logger.info(f"User said: {transcript}")
                        conversation.append({"role": "user", "content": transcript})
                elif event_type == "input_audio_buffer.speech_started":
                    logger.info("User started speaking")
                    if stream_sid:
                        await twilio_ws.send_json({
                            "event": "clear",
                            "streamSid": stream_sid
                        })
                elif event_type == "error":
                    logger.error(f"OpenAI error: {data}")
        except Exception as e:
            logger.error(f"OpenAI→Twilio error: {e}")
            stop_event.set()

    try:
        await asyncio.gather(twilio_to_openai(), openai_to_twilio())
    except Exception as e:
        logger.error(f"Media stream error: {e}")
    finally:
        await openai_ws.close()
        logger.info("Session ended")
        
        # 통화 종료 후 요청 처리
        if conversation:
            logger.info(f"📊 대화 {len(conversation)}건 저장 중...")
            try:
                result = process_call_end(conversation)
                logger.info(f"✅ 요청 처리 완료: {len(result.get('requests', []))}개")
            except Exception as e:
                logger.error(f"요청 처리 실패: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
