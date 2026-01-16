from __future__ import annotations
import asyncio, base64, json, logging, time
from typing import Any, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.settings import settings
from app.lang import iso_for
from app.utils.audio import convert_to_wav, cleanup_audio_file
from app.stt.whisper_stt import transcribe_wav
from app.tts.mms_tts import synth_mms
from app.db import connect, init_db, ensure_schemes_loaded, get_or_create_session, save_session, add_message
from app.memory import extract_profile_updates, apply_updates_with_contradiction
from app.agent.agent import run_agent_turn

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("sevasetu")
logger.info(
    "Startup stt=%s tts=%s llm=%s sqlite=%s log=%s",
    settings.stt_provider,
    settings.tts_provider,
    settings.llm_provider or "none",
    settings.sqlite_path,
    settings.log_level,
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

conn = connect()
init_db(conn)
ensure_schemes_loaded(conn)

@app.get("/health")
def health():
    return {"ok": True, "stt": settings.stt_provider, "tts": settings.tts_provider, "db": "sqlite"}

async def _send(ws: WebSocket, payload: Dict[str, Any]):
    await ws.send_text(json.dumps(payload, ensure_ascii=False))

async def _with_timeout(name: str, coro, timeout_s: int):
    """Run an awaitable with a timeout; raise TimeoutError with stage context."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except asyncio.TimeoutError as e:
        raise TimeoutError(f"{name} timed out after {timeout_s}s") from e

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = None
    language = "Marathi"
    logger.info("WS connected")

    try:
        while True:
            raw = await ws.receive_text()
            logger.debug("WS message bytes=%d", len(raw))
            msg = json.loads(raw)
            msg_type = msg.get("type")
            logger.debug("WS message type=%s", msg_type)

            if msg_type == "hello":
                session_id = msg.get("sessionId") or "sess_default"
                # Demo is Marathi-only; keep this fixed to avoid STT language drift
                language = "Marathi"
                logger.info("Hello session_id=%s language=%s", session_id, language)
                await _send(ws, {"type":"hello_ack","sessionId":session_id,"language":language})
                continue

            if msg_type != "audio":
                logger.debug("Ignoring message type=%s", msg_type)
                continue

            if not session_id:
                session_id = msg.get("sessionId") or "sess_default"

            wav_path = None
            try:
                b64 = msg.get("data","")
                mime = msg.get("mimeType","audio/webm")
                audio_bytes = base64.b64decode(b64) if b64 else b""
                logger.info("Audio received session_id=%s bytes=%d mime=%s", session_id, len(audio_bytes), mime)
                await _send(ws, {"type":"agent_event","event":"AUDIO_RECEIVED"})

                t0 = time.perf_counter()
                wav_path = await convert_to_wav(audio_bytes, mime_type=mime)
                logger.debug("Audio converted path=%s ms=%.0f", wav_path, (time.perf_counter() - t0) * 1000)

                await _send(ws, {"type":"agent_event","event":"STT_START"})
                t0 = time.perf_counter()
                text, conf = await _with_timeout(
                    "STT",
                    asyncio.to_thread(transcribe_wav, str(wav_path), iso_for(language)),
                    int(getattr(settings, "stt_timeout_s", 25)),
                )
                logger.info("STT done chars=%d conf=%.2f ms=%.0f", len(text), conf, (time.perf_counter() - t0) * 1000)
                logger.debug("STT text=%s", text)
                await _send(ws, {"type":"agent_event","event":"STT_DONE","payload":{"confidence": float(conf)}})
                await _send(ws, {"type":"stt_result","text": text, "confidence": conf})

                if not (text or "").strip():
                    logger.info("STT empty result session_id=%s", session_id)
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
                if updates:
                    logger.debug("Profile updates=%s", updates)
                if conflict:
                    logger.info("Profile conflict field=%s", conflict.get("field"))

                if conflict:
                    save_session(conn, session_id, language, profile, pending, state)
                    reply = f"तुम्ही आधी {conflict['field']} = {conflict['old']} सांगितले होते, आता {conflict['new']} म्हणत आहात. कोणते बरोबर आहे?"
                    audio_out, out_mime = await asyncio.to_thread(synth_mms, reply, language)
                    tts_b64 = base64.b64encode(audio_out).decode("utf-8")
                    await _send(ws, {"type":"assistant_message","text":reply,"ui":{"ui_intent":"question","questions_mr":["जुने की नवीन?"],"cards":[]},"ttsAudioB64":tts_b64,"ttsMime":out_mime})
                    continue

                await _send(ws, {"type":"agent_event","event":"AGENT_START"})
                logger.info("Agent start session_id=%s text_len=%d", session_id, len(text))
                assistant_text, ui_payload, tool_trace, pending2, state2 = await _with_timeout(
                    "AGENT",
                    run_agent_turn(
                        conn=conn,
                        session_id=session_id,
                        utterance=text,
                        stt_confidence=float(conf),
                        profile=profile,
                        pending=pending,
                        state=state,
                    ),
                    int(getattr(settings, "agent_timeout_s", 45)),
                )

                pending = pending2
                state = state2
                logger.info("Agent done tool_events=%d ui_intent=%s", len(tool_trace), ui_payload.get("ui_intent"))
                await _send(ws, {"type":"agent_event","event":"AGENT_DONE","payload":{"ui_intent": ui_payload.get("ui_intent")}})
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
                t0 = time.perf_counter()
                audio_out, out_mime = await _with_timeout(
                    "TTS",
                    asyncio.to_thread(synth_mms, assistant_text, language),
                    int(getattr(settings, "tts_timeout_s", 25)),
                )
                audio_out = audio_out or b""
                logger.info("TTS done bytes=%d ms=%.0f", len(audio_out), (time.perf_counter() - t0) * 1000)
                await _send(ws, {"type":"agent_event","event":"TTS_DONE","payload":{"bytes": len(audio_out)}})
                tts_b64 = base64.b64encode(audio_out).decode("utf-8")

                await _send(ws, {"type":"assistant_message","text":assistant_text,"ui":ui_payload,"ttsAudioB64":tts_b64,"ttsMime":out_mime})

            except Exception as e:
                logger.exception("Turn error session_id=%s", session_id)
                stage = "TURN"
                msg_txt = str(e)
                if isinstance(e, TimeoutError):
                    stage = "TIMEOUT"
                await _send(ws, {"type":"agent_event","event":"ERROR","payload":{"stage": stage, "message": msg_txt}})
                reply = "क्षमस्व, थोडा वेळ लागला/अडचण आली. कृपया पुन्हा एकदा बोला."
                audio_out, out_mime = await asyncio.to_thread(synth_mms, reply, language)
                tts_b64 = base64.b64encode(audio_out).decode("utf-8")
                await _send(ws, {"type":"assistant_message","text":reply,"ui":{"ui_intent":"error","questions_mr":["पुन्हा बोला."],"cards":[]},"ttsAudioB64":tts_b64,"ttsMime":out_mime})
            finally:
                if wav_path:
                    cleanup_audio_file(wav_path)

    except WebSocketDisconnect:
        logger.info("WS disconnected session_id=%s", session_id)
