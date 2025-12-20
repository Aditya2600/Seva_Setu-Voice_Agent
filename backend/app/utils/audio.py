from __future__ import annotations
import asyncio, shutil, subprocess, tempfile
from functools import partial
from pathlib import Path

def _convert_sync(input_bytes: bytes, mime_type: str = "audio/webm") -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="sevasetu_audio_"))
    mt = (mime_type or "").lower()
    ext = ".dat"
    if "webm" in mt: ext = ".webm"
    elif "mp4" in mt or "m4a" in mt: ext = ".mp4"
    elif "wav" in mt: ext = ".wav"
    elif "mp3" in mt: ext = ".mp3"
    elif "ogg" in mt: ext = ".ogg"

    in_path = tmp_dir / f"input{ext}"
    out_path = tmp_dir / "audio.wav"
    in_path.write_bytes(input_bytes)

    cmd = [
        "ffmpeg","-y","-hide_banner","-loglevel","error",
        "-i", str(in_path),
        "-vn","-ac","1","-ar","16000","-acodec","pcm_s16le",
        str(out_path)
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0 or not out_path.exists():
        err = proc.stderr.decode("utf-8", errors="ignore")[:800]
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"FFmpeg failed: {err}")
    return out_path

async def convert_to_wav(input_bytes: bytes, mime_type: str = "audio/webm") -> Path:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_convert_sync, input_bytes, mime_type))

def cleanup_audio_file(file_path: Path | None):
    if not file_path:
        return
    try:
        parent = file_path.parent
        if parent.name.startswith("sevasetu_audio_"):
            shutil.rmtree(parent, ignore_errors=True)
    except Exception:
        pass
