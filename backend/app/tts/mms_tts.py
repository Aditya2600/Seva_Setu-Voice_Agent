from __future__ import annotations
from functools import lru_cache
from typing import Tuple
import io, logging, time
import numpy as np
import soundfile as sf

logger = logging.getLogger("sevasetu")

@lru_cache(maxsize=1)
def _load():
    import torch
    from transformers import VitsModel, AutoTokenizer
    device = (
        "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
        else ("cuda" if torch.cuda.is_available() else "cpu")
    )
    model_id="facebook/mms-tts-mar"
    logger.info("Loading MMS TTS model=%s device=%s", model_id, device)
    tok=AutoTokenizer.from_pretrained(model_id)
    model=VitsModel.from_pretrained(model_id)
    model.to(device); model.eval()
    return device, tok, model

def synth_mms(text: str, language: str = "Marathi") -> Tuple[bytes, str]:
    t0 = time.perf_counter()
    text=(text or "").strip()
    if not text:
        silent=np.zeros(16000,dtype=np.float32)
        buf=io.BytesIO()
        sf.write(buf, silent, 16000, format="WAV")
        audio = buf.getvalue()
        logger.debug("TTS empty input -> silence bytes=%d ms=%.0f", len(audio), (time.perf_counter() - t0) * 1000)
        return audio, "audio/wav"
    device, tok, model=_load()
    import torch
    inputs=tok(text, return_tensors="pt")
    # Guardrail: avoid pathological long TTS requests (prevents hangs)
    if len(text) > 500:
        text = text[:500]
        inputs = tok(text, return_tensors="pt")
    inputs={k:v.to(device) for k,v in inputs.items()}
    with torch.no_grad():
        wav=model(**inputs).waveform[0].detach().cpu().numpy().astype(np.float32)
    # Safety: replace NaNs/Infs if any
    wav = np.nan_to_num(wav, nan=0.0, posinf=0.0, neginf=0.0)
    sr=int(getattr(model.config,"sampling_rate",16000) or 16000)
    buf=io.BytesIO()
    sf.write(buf, wav, sr, format="WAV")
    audio = buf.getvalue()
    logger.debug(
        "TTS done chars=%d bytes=%d sr=%d ms=%.0f",
        len(text),
        len(audio),
        sr,
        (time.perf_counter() - t0) * 1000,
    )
    return audio, "audio/wav"
