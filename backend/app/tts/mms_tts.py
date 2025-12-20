from __future__ import annotations
from functools import lru_cache
from typing import Tuple
import io
import numpy as np
import soundfile as sf

@lru_cache(maxsize=1)
def _load():
    import torch
    from transformers import VitsModel, AutoTokenizer
    device="mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    model_id="facebook/mms-tts-mar"
    tok=AutoTokenizer.from_pretrained(model_id)
    model=VitsModel.from_pretrained(model_id)
    model.to(device); model.eval()
    return device, tok, model

def synth_mms(text: str, language: str="Marathi")->Tuple[bytes,str]:
    text=(text or "").strip()
    if not text:
        silent=np.zeros(16000,dtype=np.float32)
        buf=io.BytesIO()
        sf.write(buf, silent, 16000, format="WAV")
        return buf.getvalue(), "audio/wav"
    device, tok, model=_load()
    import torch
    inputs=tok(text, return_tensors="pt")
    inputs={k:v.to(device) for k,v in inputs.items()}
    with torch.no_grad():
        wav=model(**inputs).waveform[0].detach().cpu().numpy().astype(np.float32)
    sr=int(getattr(model.config,"sampling_rate",16000) or 16000)
    buf=io.BytesIO()
    sf.write(buf, wav, sr, format="WAV")
    return buf.getvalue(), "audio/wav"
