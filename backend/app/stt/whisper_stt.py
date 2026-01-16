from __future__ import annotations
import logging, math, time
from functools import lru_cache
from typing import Tuple, List
from faster_whisper import WhisperModel
from app.settings import settings

logger = logging.getLogger("sevasetu")

@lru_cache(maxsize=1)
def _model()->WhisperModel:
    logger.info(
        "Loading whisper model=%s device=%s compute=%s",
        settings.whisper_model,
        settings.whisper_device,
        settings.whisper_compute_type,
    )
    return WhisperModel(settings.whisper_model, device=settings.whisper_device, compute_type=settings.whisper_compute_type)

def _conf(segs: List)->float:
    probs=[]
    for s in segs:
        lp=getattr(s,"avg_logprob",-2.5)
        nsp=getattr(s,"no_speech_prob",0.0)
        try: p_lp=math.exp(lp) if lp<0 else 1.0
        except Exception: p_lp=0.2
        p=float(p_lp)*(1.0-float(nsp))
        probs.append(max(0.0,min(1.0,p)))
    return float(sum(probs)/len(probs)) if probs else 0.0

def transcribe_wav(wav_path: str, language_iso: str="mr")->Tuple[str,float]:
    t0 = time.perf_counter()
    logger.debug("STT transcribe start wav=%s lang=%s", wav_path, language_iso)
    model=_model()
    segments, _info = model.transcribe(
        wav_path,
        language=language_iso,
        task="transcribe",
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=350),
        beam_size=1,
        condition_on_previous_text=False,
        temperature=0.0
    )
    segs=list(segments)
    text=" ".join([(s.text or "").strip() for s in segs]).strip()
    conf=_conf(segs)
    logger.debug("STT segments=%d chars=%d conf=%.2f ms=%.0f", len(segs), len(text), conf, (time.perf_counter() - t0) * 1000)
    # If super low confidence treat as empty
    if not text or conf<0.18:
        return "", 0.0
    return text, conf
