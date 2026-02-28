"""
Phone Agent: OpenAI Realtime API + Twilio
Real-time speech-to-speech voice agent over phone calls.
"""
import os
import json
import asyncio
import base64
import logging
from urllib.parse import urlsplit

import audioop
import uvicorn
from fastapi import FastAPI, WebSocket, Request, Response
from fastapi.websockets import WebSocketDisconnect
import websockets

from twilio.twiml.voice_response import VoiceResponse, Connect

# Configuration
PORT = int(os.getenv("PORT", 8082))
HOST = "0.0.0.0"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PUBLIC_URL = os.getenv("PUBLIC_URL_REALTIME")

app = FastAPI()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ── Customize these ──────────────────────────────────────────
SYSTEM_PROMPT = """당신은 매일 아침 전화를 걸어주는 AI 모닝콜 비서 '하나'예요.

규칙:
- 전화가 연결되면 먼저 밝고 따뜻하게 아침 인사를 해주세요
- 오늘 날짜와 요일을 알려주세요
- 오늘 하루 계획이나 할 일이 있는지 물어봐주세요
- 응답은 2-3문장으로 짧고 자연스럽게
- 격려와 응원의 말로 하루를 시작할 수 있게 해주세요
- 반말로 친근하게 대화해주세요

첫 인사 예시: "좋은 아침! 나는 AI 모닝콜 비서 하나야. 잘 잤어? 오늘 금요일인데, 오늘 뭐 할 계획 있어?"
"""

VOICE = "shimmer"  # alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar
# ─────────────────────────────────────────────────────────────

OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview"


def twilio_to_openai_audio(mulaw_chunk: bytes) -> bytes:
    """Twilio mu-law 8kHz → OpenAI PCM16 16kHz."""
    pcm_8k = audioop.ulaw2lin(mulaw_chunk, 2)
    pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)
    return pcm_16k


def openai_to_twilio_audio(pcm16_chunk: bytes) -> bytes:
    """OpenAI PCM16 24kHz → Twilio mu-law 8kHz."""
    pcm_8k, _ = audioop.ratecv(pcm16_chunk, 2, 1, 24000, 8000, None)
    mulaw = audioop.lin2ulaw(pcm_8k, 2)
    return mulaw


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
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "modalities": ["text", "audio"],
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
                    mulaw_audio = base64.b64decode(data["media"]["payload"])
                    pcm16_audio = twilio_to_openai_audio(mulaw_audio)
                    encoded = base64.b64encode(pcm16_audio).decode("utf-8")
                    await openai_ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": encoded
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
                        pcm16_audio = base64.b64decode(data["delta"])
                        mulaw_audio = openai_to_twilio_audio(pcm16_audio)
                        payload = base64.b64encode(mulaw_audio).decode("utf-8")
                        await twilio_ws.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": payload}
                        })
                elif event_type == "response.audio_transcript.done":
                    transcript = data.get("transcript", "")
                    if transcript:
                        logger.info(f"AI said: {transcript}")
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = data.get("transcript", "")
                    if transcript:
                        logger.info(f"User said: {transcript}")
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


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
