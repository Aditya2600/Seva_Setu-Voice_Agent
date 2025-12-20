import os, sys, time
import sounddevice as sd
import soundfile as sf

sys.path.insert(0, os.path.abspath("."))

from app.stt.whisper_stt import transcribe_wav
from app.tts.mms_tts import synth_mms
from app.lang import iso_for

IN_WAV="smoke_input.wav"
OUT_WAV="smoke_reply.wav"
FS=16000
DUR=5

print("🎙️  बोलून दाखवा: 'मला सरकारी योजना हवी आहे. मी शेतकरी आहे.'")
audio=sd.rec(int(DUR*FS), samplerate=FS, channels=1, dtype="float32")
sd.wait()
sf.write(IN_WAV, audio, FS)
print("Saved:", IN_WAV)

t0=time.time()
text, conf = transcribe_wav(IN_WAV, iso_for("Marathi"))
print("STT:", text, conf, "t=", time.time()-t0)

reply = "तुम्ही म्हणालात: " + (text or "मला काही ऐकू आले नाही.")
audio_bytes, _mime = synth_mms(reply, "Marathi")
open(OUT_WAV,"wb").write(audio_bytes)
print("Saved:", OUT_WAV)

data, fs = sf.read(OUT_WAV)
sd.play(data, fs)
sd.wait()
print("Done")
