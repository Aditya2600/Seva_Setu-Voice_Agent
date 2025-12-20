# SevaSetu — Marathi Voice Welfare Agent

SevaSetu is a Marathi voice assistant that helps users discover welfare schemes and check eligibility. It runs a WebSocket backend for STT/agent/TTS and a small frontend for live conversations.

## Quick Start

### Backend
Requirements: Python 3.10+, `ffmpeg` on PATH.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

cp .env.example .env
# edit .env to set API keys if needed

uvicorn app.main:app --reload --port 8000
```

### Frontend
Requirements: Node 18+ (pnpm recommended).

```bash
cd frontend
pnpm install   # or npm install
pnpm dev --host --port 5173
```

Open: http://localhost:5173

## Configuration

Backend env (`backend/.env`):
- `STT_PROVIDER`, `TTS_PROVIDER` (defaults: whisper/mms).
- `SQLITE_PATH` for session + scheme cache.
- Optional Groq re-ranking:
  - `LLM_PROVIDER=groq`
  - `GROQ_API_KEY=...`
  - `GROQ_MODEL=llama-3.1-8b-instant`
  - `GROQ_BASE_URL=https://api.groq.com/openai/v1`

Frontend env (`frontend/.env`):
- `VITE_WS_URL` to point at a non-default backend (default: `ws://localhost:8000/ws`).

## Optional: Ollama
```bash
ollama pull llama3.1:8b
ollama serve
```

## Smoke Test (backend)
```bash
cd backend
source .venv/bin/activate
python scripts/smoke_stt_tts.py
```

## Docs
- Architecture: `ARCHITECTURE.md`
