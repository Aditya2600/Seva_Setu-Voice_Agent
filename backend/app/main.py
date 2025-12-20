from __future__ import annotations
import asyncio, base64, json, logging
from typing import Any, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.settings import settings
from app.lang import iso_for
from app.utils.audio import convert_to_wav, cleanup_audio_file
from app.stt.whisper_stt import transcribe_wav
from app.tts.mms_tts import synth_mms
from app.db import connect, init_db, get_or_create_session, save_session, add_message
from app.memory import extract_profile_updates, apply_updates_with_contradiction
from app.agent.agent import run_agent_turn

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("sevasetu")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

conn = connect()
init_db(conn)

@app.get("/health")
def health():
    return {"ok": True, "stt": settings.stt_provider, "tts": settings.tts_provider, "db": "sqlite"}

async def _send(ws: WebSocket, payload: Dict[str, Any]):
    await ws.send_text(json.dumps(payload, ensure_ascii=False))

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = None
    language = "Marathi"
    logger.info("WS connected")

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            if msg.get("type") == "hello":
                session_id = msg.get("sessionId") or "sess_default"
                await _send(ws, {"type":"hello_ack","sessionId":session_id,"language":language})
                continue

            if msg.get("type") != "audio":
                continue

            if not session_id:
                session_id = msg.get("sessionId") or "sess_default"

            wav_path = None
            try:
                b64 = msg.get("data","")
                mime = msg.get("mimeType","audio/webm")
                audio_bytes = base64.b64decode(b64) if b64 else b""
                await _send(ws, {"type":"agent_event","event":"AUDIO_RECEIVED"})

                wav_path = await convert_to_wav(audio_bytes, mime_type=mime)

                await _send(ws, {"type":"agent_event","event":"STT_START"})
                text, conf = await asyncio.to_thread(transcribe_wav, str(wav_path), iso_for(language))
                await _send(ws, {"type":"stt_result","text": text, "confidence": conf})

                if not (text or "").strip():
                    await _send(ws, {"type":"agent_event","event":"STT_REJECTED","payload":{"reason":"empty"}})
                    reply = "मला नीट ऐकू आलं नाही. कृपया पुन्हा हळू आणि स्पष्ट मराठीत सांगा."
                    audio_out, out_mime = await asyncio.to_thread(synth_mms, reply, language)
                    tts_b64 = base64.b64encode(audio_out).decode("utf-8")
                    await _send(ws, {"type":"assistant_message","text":reply,"ui":{"ui_intent":"error","questions_mr":["कृपया पुन्हा सांगा."],"cards":[]},"ttsAudioB64":tts_b64,"ttsMime":out_mime})
                    continue

                profile, pending, state = get_or_create_session(conn, session_id, language)
                add_message(conn, session_id, "user", text)

                updates = extract_profile_updates(text)
                profile, pending, conflict = apply_updates_with_contradiction(profile, pending, updates)

                if conflict:
                    save_session(conn, session_id, language, profile, pending, state)
                    reply = f"तुम्ही आधी {conflict['field']} = {conflict['old']} सांगितले होते, आता {conflict['new']} म्हणत आहात. कोणते बरोबर आहे?"
                    audio_out, out_mime = await asyncio.to_thread(synth_mms, reply, language)
                    tts_b64 = base64.b64encode(audio_out).decode("utf-8")
                    await _send(ws, {"type":"assistant_message","text":reply,"ui":{"ui_intent":"question","questions_mr":["जुने की नवीन?"],"cards":[]},"ttsAudioB64":tts_b64,"ttsMime":out_mime})
                    continue

                await _send(ws, {"type":"agent_event","event":"AGENT_START"})
                assistant_text, ui_payload, tool_trace, pending2, state2 = await run_agent_turn(
                    conn=conn,
                    session_id=session_id,
                    utterance=text,
                    stt_confidence=float(conf),
                    profile=profile,
                    pending=pending,
                    state=state,
                )

                pending = pending2
                state = state2
                save_session(conn, session_id, language, profile, pending, state)

                for evt in tool_trace:
                    if evt.get("type") == "tool_call":
                        await _send(ws, {"type":"tool_call","tool":evt.get("tool"),"payload":evt.get("input")})
                    elif evt.get("type") == "tool_result":
                        await _send(ws, {"type":"tool_result","tool":evt.get("tool"),"payload":evt.get("output")})
                    elif evt.get("type") == "plan":
                        await _send(ws, {"type":"agent_event","event":"PLAN","payload":evt.get("plan")})

                add_message(conn, session_id, "assistant", assistant_text)

                await _send(ws, {"type":"agent_event","event":"TTS_START"})
                audio_out, out_mime = await asyncio.to_thread(synth_mms, assistant_text, language)
                tts_b64 = base64.b64encode(audio_out).decode("utf-8")

                await _send(ws, {"type":"assistant_message","text":assistant_text,"ui":ui_payload,"ttsAudioB64":tts_b64,"ttsMime":out_mime})

            except Exception as e:
                logger.exception("Turn error")
                await _send(ws, {"type":"agent_event","event":"ERROR","payload":{"message":str(e)}})
                reply = "क्षमस्व, तांत्रिक अडचण आली. कृपया पुन्हा प्रयत्न करा."
                audio_out, out_mime = await asyncio.to_thread(synth_mms, reply, language)
                tts_b64 = base64.b64encode(audio_out).decode("utf-8")
                await _send(ws, {"type":"assistant_message","text":reply,"ui":{"ui_intent":"error","questions_mr":["पुन्हा बोला."],"cards":[]},"ttsAudioB64":tts_b64,"ttsMime":out_mime})
            finally:
                cleanup_audio_file(wav_path)

    except WebSocketDisconnect:
        logger.info("WS disconnected")
